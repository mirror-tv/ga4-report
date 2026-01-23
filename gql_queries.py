from gql import gql


GET_POSTS_BY_SLUGS = gql("""
    query GetPostsBySlugs($slugs: [String!]) {
      posts(where: { slug: { in: $slugs } }) {
          id
          heroImage {
              resized {
                  w480
                  w800
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