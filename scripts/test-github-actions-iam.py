#!/usr/bin/env python3
"""Small, dependency-free contracts for the CI-only AWS federation root."""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1] / 'infra/terraform/github-actions'


class FederationContract(unittest.TestCase):
    def test_scoped_roles_and_separate_state(self):
        path = ROOT / 'main.tf.json'
        self.assertTrue(path.exists(), 'GitHub Actions IAM root is missing')
        config = json.loads(path.read_text())
        self.assertEqual(config['terraform']['backend']['s3']['key'], 'platform/github-actions/terraform.tfstate')
        resources = config['resource']
        self.assertEqual(set(resources), {'aws_iam_openid_connect_provider', 'aws_iam_role', 'aws_iam_role_policy'})
        provider = resources['aws_iam_openid_connect_provider']['github']
        self.assertEqual(provider['url'], 'https://token.actions.githubusercontent.com')
        self.assertEqual(provider['client_id_list'], ['sts.amazonaws.com'])
        roles = resources['aws_iam_role']
        self.assertEqual(len(roles), 5)
        for name, role in roles.items():
            policy = json.loads(role['assume_role_policy'])
            statement = policy['Statement'][0]
            self.assertEqual(statement['Action'], 'sts:AssumeRoleWithWebIdentity')
            conditions = statement['Condition']['StringEquals']
            self.assertEqual(conditions['token.actions.githubusercontent.com:aud'], 'sts.amazonaws.com')
            for subject in conditions['token.actions.githubusercontent.com:sub']:
                self.assertNotIn('*', subject)
                self.assertRegex(subject, r'^repo:[^:]+:ref:refs/heads/(main|develop)$')
            permission = json.loads(resources['aws_iam_role_policy'][name]['policy'])
            for entry in permission['Statement']:
                self.assertNotIn('*', entry['Action'], 'Never grant service-wide/admin actions')
                if name.endswith('_ecr'):
                    for action in entry['Action']:
                        self.assertTrue(action.startswith('ecr:'))
                        self.assertNotIn('Delete', action)


if __name__ == '__main__':
    unittest.main()
