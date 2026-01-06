import os
import re
import json
import sys
import codecs
from gql import gql
from datetime import datetime, timedelta
from google.cloud import storage
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange
from google.analytics.data_v1beta.types import Dimension
from google.analytics.data_v1beta.types import Metric
from google.analytics.data_v1beta.types import RunReportRequest
from gql_client import GraphQLClient

def get_article(response):
    graphql_client = GraphQLClient()

    try:
        gql_client = graphql_client.get_authenticated_client()
        print("Using authenticated GraphQL client")
    except ValueError as e:
        print(f"Authentication credentials not provided, using basic client: {e}")
        gql_client = graphql_client.get_client()
    except Exception as e:
        print(f"Authentication failed, using basic client: {e}")
        gql_client = graphql_client.get_client()

    report = {  'articles': [] ,
                'yt': [] }
    id_bucket = []
    yt_id = []
    rows = 0
    yt_rows = 0
    exclusive = ["aboutus", "ad-sales", "adsales", "biography", "complaint", "faq", "press-self-regulation", "privacy", "standards", "webauthorization", "aboutus"]
    for article in response.rows:
        uri = article.dimension_values[1].value
        id_match = re.match('/story/([\w-]+)', uri)
        if id_match:
            post_id = id_match.group(1)
            if post_id in id_bucket:
                continue
            if post_id and post_id[:3] != 'mm-' and post_id not in exclusive:
                post_gql = '''
                    query {
                      posts(where: { slug: { equals: "%s"}}, orderBy: [{ publishTime: desc }]) {
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
                    }''' % (post_id)
                query = gql(post_gql)
                post = gql_client.execute(query)
                if isinstance(post, dict) and "posts" in post and len(post['posts']) > 0:
                    rows = rows + 1
                    if rows <= 30:
                        article_data = post['posts'][0].copy()
                        article_data.pop('exclusive', None)
                        if 'heroImage' in article_data and article_data['heroImage']:
                            if 'resized' in article_data['heroImage'] and article_data['heroImage']['resized']:
                                resized = article_data['heroImage']['resized']
                                article_data['heroImage'] = {
                                    'urlTinySized': resized.get('w480'),
                                    'urlMobileSized': resized.get('w800')
                                }
                            else:
                                article_data['heroImage'] = None
                        report['articles'].append(article_data)
                    if 'source' in post['posts'][0] and post['posts'][0]['source'] == 'yt' and post['posts'][0]['id'] not in yt_id:
                        yt_id.append(post['posts'][0]['id'])
                        yt_data = post['posts'][0].copy()
                        yt_data.pop('exclusive', None)
                        if 'heroImage' in yt_data and yt_data['heroImage']:
                            if 'resized' in yt_data['heroImage'] and yt_data['heroImage']['resized']:
                                resized = yt_data['heroImage']['resized']
                                yt_data['heroImage'] = {
                                    'urlTinySized': resized.get('w480'),
                                    'urlMobileSized': resized.get('w800')
                                }
                            else:
                                yt_data['heroImage'] = None
                        report['yt'].append(yt_data)
                        yt_rows = yt_rows + 1
                id_bucket.append(post_id)
        if rows > 30 and yt_rows > 10:
            break
    return report

def popular_report(property_id):
    """Runs a simple report on a Google Analytics 4 property."""
    # Using a default constructor instructs the client to use the credentials
    # specified in GOOGLE_APPLICATION_CREDENTIALS environment variable.
    if sys.stdout:
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    try:    
        client = BetaAnalyticsDataClient()
    except Exception as e:
        print(f"Failed to initialize client: {type(e).__name__}")
        print(f"Error details: {str(e)}")
        return "failed"
    
    current_time = datetime.now()
    start_datetime = current_time - timedelta(days=2)
    start_date = datetime.strftime(start_datetime, '%Y-%m-%d')
    end_date = datetime.strftime(current_time, '%Y-%m-%d')

    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[
		    Dimension(name="pageTitle"),
		    Dimension(name="pagePath")
		],
        metrics=[Metric(name="screenPageViews")],
        date_ranges=[DateRange(start_date=start_date, end_date="today")],
    )
    try:
        response = client.run_report(request)
    except Exception as e:
        print("Failed to get GA report")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        return "failed"

    report = get_article(response)
    gcs_path = os.environ['GCS_PATH']
    bucket = os.environ['BUCKET']
    popular_report = { "report": report['articles'], "start_date": start_date, "end_date": end_date, "generate_time": datetime.strftime(current_time, '%Y-%m-%d %H:%M')}
    popular_video = { "report": report['yt'], "start_date": start_date, "end_date": end_date, "generate_time": datetime.strftime(current_time, '%Y-%m-%d %H:%M')}
    upload_data(bucket, json.dumps(popular_report, ensure_ascii=False).encode('utf8'), 'application/json', gcs_path + 'popularlist.json')
    upload_data(bucket, json.dumps(popular_video, ensure_ascii=False).encode('utf8'), 'application/json', gcs_path + 'popular-videonews-list.json')
    return "Ok"

def upload_data(bucket_name: str, data: str, content_type: str, destination_blob_name: str):
    '''Uploads a file to the bucket.'''
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_string(
        data=bytes(data),
        content_type=content_type, client=storage_client)
    blob.content_language = 'zh'
    blob.cache_control = 'max-age=300,public'
    blob.patch()

if __name__ == "__main__":  
	if 'GA_RESOURCE_ID' in os.environ:
		ga_id = os.environ['GA_RESOURCE_ID']
	else:
		ga_id = "311149968"
	popular_report(ga_id)
