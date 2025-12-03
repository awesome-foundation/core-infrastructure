#!/usr/bin/env python3
# Copyright 2025 Luka Kladarić, Chaos Guru
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import boto3
import yaml
import click

class BiMap:
    # BiMap implementation to store group ID to name mappings
    def __init__(self):
        self.id_to_name = {}
        self.name_to_id = {}

    def add(self, group_id, group_name):
        assert group_id not in self.id_to_name, f"Group ID {group_id} already exists"
        assert group_name not in self.name_to_id, f"Group name {group_name} already exists"

        self.id_to_name[group_id] = group_name
        self.name_to_id[group_name] = group_id

    def get_name(self, group_id):
        assert group_id in self.id_to_name, f"Group ID {group_id} does not exist"
        return self.id_to_name.get(group_id)

    def get_id(self, group_name):
        assert group_name in self.name_to_id, f"Group name {group_name} does not exist"
        return self.name_to_id.get(group_name)

    def __len__(self):
        return len(self.id_to_name)

    def __str__(self):
        return self.name_to_id.__str__()

    def __repr__(self):
        return str(self)

class AWSIdentityManager:
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.identity_store_client = boto3.client('identitystore')
        self.sso_admin_client = boto3.client('sso-admin')
        self.identity_store_id = self.get_identity_store_id()
        self.desired_users = {}
        self.current_users = {}
        self.groups = BiMap()
        self.metrics = {
            'created': 0,
            'deleted': 0,
            'verified': 0,
            'errors': 0
        }

    def load_desired_users(self, yaml_file):
        with open(yaml_file, 'r') as file:
            self.desired_users = yaml.safe_load(file)
        if not isinstance(self.desired_users, dict):
            self.desired_users = {}

    def get_identity_store_id(self):
        response = self.sso_admin_client.list_instances()
        return response['Instances'][0]['IdentityStoreId']

    def load_current_state(self):
        self.load_groups()
        self.load_users_and_groups()

    def load_groups(self):
        response = self.identity_store_client.list_groups(IdentityStoreId=self.identity_store_id)
        for group in response['Groups']:
            self.groups.add(group['GroupId'], group['DisplayName'])

    def load_users_and_groups(self):
        # Load users and their groups
        response = self.identity_store_client.list_users(IdentityStoreId=self.identity_store_id)
        for user in response['Users']:
            user_groups_with_membership = self.get_groups_for_user(user['UserId'])
            user_groups = list(user_groups_with_membership.keys())
            self.current_users[user['UserName']] = {
                'UserId': user['UserId'],
                'Groups': user_groups,
                'MembershipIds': user_groups_with_membership
            }

    def get_groups_for_user(self, user_id):
        # Returns a dictionary of group name to membership id
        response = self.identity_store_client.list_group_memberships_for_member(
            IdentityStoreId=self.identity_store_id, MemberId={'UserId': user_id})
        result = {}
        for membership in response.get('GroupMemberships', []):
            result[self.groups.get_name(membership['GroupId'])] = membership['MembershipId']
        return result

    def sync_users(self):
        # Compare desired users with current users and act accordingly
        users_to_create = [user for user in self.desired_users if user not in self.current_users]
        users_to_delete = [user for user in self.current_users if user not in self.desired_users]
        users_to_verify = [user for user in self.desired_users if user in self.current_users]

        for user in users_to_create:
            self.create_user(user, self.desired_users[user])

        for user in users_to_delete:
            self.delete_user(user)

        for user in users_to_verify:
            self.verify_user_groups(user, self.desired_users[user]['groups'])

    def split_full_name(self, display_name):
        # Split the display name into first and last name
        parts = display_name.split()
        return {'GivenName': parts[0], 'FamilyName': parts[-1]}

    def create_user(self, email, user_info):
        # Create a new user and set their groups
        if self.dry_run:
            click.echo(f"DRY RUN: {email} would have been created with groups {user_info['groups']}")
            self.metrics['created'] += 1
            return

        try:
            click.echo(f"{email} Inviting to org and granting groups {user_info['groups']}")
            response = self.identity_store_client.create_user(
                IdentityStoreId=self.identity_store_id,
                UserName=email,
                DisplayName=user_info['display_name'],
                Name=self.split_full_name(user_info['display_name']),
                Emails=[{'Value': email, 'Type': 'work', 'Primary': True}]
            )
            self.load_users_and_groups() # Resync users so verify_user_groups works
            self.verify_user_groups(email, user_info['groups'])
            self.metrics['created'] += 1
        except Exception as e:
            click.echo(f"Error creating user {email}: {e}")
            self.metrics['errors'] += 1

    def delete_user(self, email):
        if self.dry_run:
            click.echo(f"DRY RUN: {email} Would have been deleted")
            self.metrics['deleted'] += 1
            return

        try:
            click.echo(f"{email} is being removed")
            userid = self.current_users[email]['UserId']
            self.identity_store_client.delete_user(IdentityStoreId=self.identity_store_id, UserId=userid)
            self.metrics['deleted'] += 1
        except Exception as e:
            click.echo(f"Error deleting user {email}: {e}")
            self.metrics['errors'] += 1

    def verify_user_groups(self, email, groups):
        # Verify that the user is in the correct groups
        userid = self.current_users[email]['UserId']

        # Implementation of group verification logic goes here
        desired_groups = sorted(groups)
        current_groups = sorted(self.current_users[email]['Groups'])

        groups_to_add = [group for group in desired_groups if group not in current_groups]
        groups_to_remove = [group for group in current_groups if group not in desired_groups]

        if len(groups_to_add) == 0 and len(groups_to_remove) == 0:
            # click.echo(f"{email} Groups are up to date: {current_groups}")
            self.metrics['verified'] += 1
            return

        if self.dry_run:
            click.echo(f"DRY RUN: {email} Would have updated groups, adding: {groups_to_add}, removing: {groups_to_remove}")
            self.metrics['verified'] += 1
            return

        try:
            if len(groups_to_add) > 0:
                click.echo(f"{email} Adding groups: {groups_to_add}")
                for gta in groups_to_add:
                    self.identity_store_client.create_group_membership(
                        IdentityStoreId=self.identity_store_id,
                        GroupId=self.groups.get_id(gta),
                        MemberId={'UserId': userid}
                    )

            if len(groups_to_remove) > 0:
                click.echo(f"{email} Removing groups: {groups_to_remove}")
                for gtr in groups_to_remove:
                    membership_id = self.current_users[email]['MembershipIds'][gtr]
                    self.identity_store_client.delete_group_membership(
                        IdentityStoreId=self.identity_store_id,
                        MembershipId=membership_id
                    )
            self.metrics['verified'] += 1
        except Exception as e:
            click.echo(f"Error verifying groups for user {email}: {e}")
            self.metrics['errors'] += 1

    def report_metrics(self):
        if self.dry_run:
            click.echo("DRY RUN Sync operation completed with the following metrics:")
        else:
            click.echo("Sync operation completed with the following metrics:")
        for metric, count in self.metrics.items():
            click.echo(f"{metric.capitalize()}: {count}")

@click.command()
@click.argument('filename')
@click.option('--dry-run', is_flag=True, help="Simulate the sync process without making any changes.")
def sync_users(filename, dry_run):
    manager = AWSIdentityManager(dry_run=dry_run)
    manager.load_desired_users(filename)
    manager.load_current_state()
    manager.sync_users()
    manager.report_metrics()

if __name__ == '__main__':
    sync_users()
