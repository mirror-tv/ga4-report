from gql import gql


GET_POSTS_BY_SLUGS = gql("""
    query GetPostsBySlugs($slugs: [String!]) {
      posts(where: { slug: { in: $slugs } }) {
          id
          heroImage {
              resized {
                  original
              }
          }
          name
          publishTime
          slug
          source
          exclusive
      }
    }
""")