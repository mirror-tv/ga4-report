import os
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport


class GraphQLClient:

    def __init__(self):
        self.endpoint = os.environ.get('GQL_ENDPOINT')
        self.username = os.environ.get('GQL_USERNAME')
        self.password = os.environ.get('GQL_PASSWORD')

        if not self.endpoint:
            raise ValueError("GQL_ENDPOINT environment variable is required")

    def get_client(self) -> Client:
        transport = RequestsHTTPTransport(url=self.endpoint)
        return Client(transport=transport, fetch_schema_from_transport=False)

    def get_authenticated_client(self) -> Client:
        if not self.username or not self.password:
            raise ValueError("GQL_USERNAME and GQL_PASSWORD are required for authentication")

        token = self._authenticate()
        transport = RequestsHTTPTransport(
            url=self.endpoint,
            headers={"Authorization": f"Bearer {token}"}
        )
        return Client(transport=transport, fetch_schema_from_transport=False)

    def _authenticate(self) -> str:
        mutation = gql("""
            mutation Authenticate($email: String!, $password: String!) {
                authenticateUserWithPassword(email: $email, password: $password) {
                    ... on UserAuthenticationWithPasswordSuccess {
                        sessionToken
                    }
                    ... on UserAuthenticationWithPasswordFailure {
                        message
                    }
                }
            }
        """)

        client = self.get_client()
        result = client.execute(
            mutation,
            variable_values={
                "email": self.username,
                "password": self.password
            }
        )

        auth_result = result.get("authenticateUserWithPassword")
        if not auth_result:
            raise Exception("Authentication failed: No response from server")

        if "sessionToken" in auth_result:
            print(f"Keystone authentication successful for user: {self.username}")
            return auth_result["sessionToken"]
        else:
            error_msg = auth_result.get("message", "Unknown error")
            raise Exception(f"Authentication failed: {error_msg}")
