"""Adapter layer for external systems.

Each module exposes a small interface that the agent layer depends on.
The current implementations are realistic mocks. Swap them for real
LDAP/Jira/Okta clients and the agents do not change.
"""
