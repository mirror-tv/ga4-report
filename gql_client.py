import os
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport


class GraphQLClient:
    def __init__(self):
        self.endpoint = os.environ.get('GQL_ENDPOINT')
        self.username = os.environ.get('GQL_USERNAME')
        self.password = os.environ.get('GQL_PASSWORD')
        
        if not self.endpoint:
            raise ValueError("GQL_ENDPOINT environment variable is required")

    def get_client(self) -> Client:
        transport = AIOHTTPTransport(url=self.endpoint)
        return Client(transport=transport, fetch_schema_from_transport=False)
    
    async def get_authenticated_client(self) -> Client:
        if not self.username or not self.password:
            print("Credentials not found, returning basic client")
            return self.get_client()

        token = await self._authenticate()
        transport = AIOHTTPTransport(
            url=self.endpoint,
            headers={"Authorization": f"Bearer {token}"}
        )
        print("Created authenticated GraphQL client")
        return Client(transport=transport, fetch_schema_from_transport=False)
    
    async def _authenticate(self) -> str:
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
        try:
            async with client as session:
                result = await session.execute(
                    mutation,
                    variable_values={
                        "email": self.username,
                        "password": self.password
                    }
                )
                auth_result = result.get("authenticateUserWithPassword")
                if auth_result and "sessionToken" in auth_result:
                    print(f"Keystone authentication successful for user: {self.username}")
                    return auth_result["sessionToken"]
                else:
                    error_msg = auth_result.get("message", "Unknown error") if auth_result else "No response"
                    raise Exception(f"Authentication failed: {error_msg}")
        except Exception as e:
            print(f"Failed to authenticate: {e}")
            raise