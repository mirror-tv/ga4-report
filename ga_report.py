import os
import re
import json
import sys
import codecs
from gql.transport.aiohttp import AIOHTTPTransport
from gql import gql, Client
from datetime import datetime, timedelta
from google.cloud import datastore
from google.oauth2 import service_account
from google.cloud import storage
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange
from google.analytics.data_v1beta.types import Dimension
from google.analytics.data_v1beta.types import Metric
from google.analytics.data_v1beta.types import RunReportRequest

def get_article(response):
    GQL_ENDPOINT = os.environ['GQL_ENDPOINT']
    gql_transport = AIOHTTPTransport(url=GQL_ENDPOINT)
    gql_client = Client(transport=gql_transport,
                        fetch_schema_from_transport=False)
    report = {  'articles': [] , 
                'yt': [] }
    rows = 0
    yt_rows = 0
    exclusive = ["aboutus", "ad-sales", "biography", "complaint", "faq", "press-self-regulation", "privacy", "standards", "webauthorization", "aboutus"]
    for article in response.rows:
        #writer.writerow([row.dimension_values[0].value, row.dimension_values[1].value.encode('utf-8'), row.metric_values[0].value])
        uri = article.dimension_values[1].value
        id_match = re.match('/story/([\w-]+)', uri)
        if id_match:
            post_id = id_match.group(1)
            print(post_id)
            if post_id and post_id[:3] != 'mm-' and post_id not in exclusive:
                post_gql = '''
                    query { 
                      allPosts(where: { slug: "%s"}, orderBy: "publishTime_DESC") {
                          id
                          heroImage {
                              urlTinySized
                              urlMobileSized
                          }
                          name
                          publishTime
                          slug
                          source
                     }
                    }''' % (post_id)
                query = gql(post_gql)
                post = gql_client.execute(query)
                if isinstance(post, dict) and "allPosts" in post and len(post['allPosts']) > 0:
                    print(post['allPosts'][0])
                    rows = rows + 1
                    if rows <= 10:
                        report['articles'].append(post['allPosts'][0])
                    if 'source' in post['allPosts'][0] and post['allPosts'][0]['source'] == 'yt':
                        report['yt'].append(post['allPosts'][0])
                        yt_rows = yt_rows + 1
        if rows > 10 and yt_rows > 10:
            break
        #report.append({'title': row.dimension_values[0].value, 'uri': row.dimension_values[1].value, 'count': row.metric_values[0].value})
    return report

def popular_report(property_id):
    """Runs a simple report on a Google Analytics 4 property."""
    # TODO(developer): Uncomment this variable and replace with your
    #  Google Analytics 4 property ID before running the sample.
    # property_id = "311149968"

    # Using a default constructor instructs the client to use the credentials
    # specified in GOOGLE_APPLICATION_CREDENTIALS environment variable.
    if sys.stdout:
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    client = BetaAnalyticsDataClient()

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
    print("report result")
    try:
        response = client.run_report(request)
    except:
        print("Failed to get GA report")
        return "failed"
    print(response)

    report = get_article(response)
    gcs_path = os.environ['GCS_PATH']
    bucket = os.environ['BUCKET']
    popular_report = { "report": report['articles'], "start_date": start_date, "end_date": end_date, "generate_time": datetime.strftime(current_time, '%Y-%m-%d %H:%m')}
    popular_video = { "report": report['yt'], "start_date": start_date, "end_date": end_date, "generate_time": datetime.strftime(current_time, '%Y-%m-%d %H:%m')}
    upload_data(bucket, json.dumps(popular_report, ensure_ascii=False).encode('utf8'), 'application/json', gcs_path + 'popularlist.json')
    upload_data(bucket, json.dumps(popular_video, ensure_ascii=False).encode('utf8'), 'application/json', gcs_path + 'popular-videonews-list.json')
    return "Ok"

def upload_data(bucket_name: str, data: str, content_type: str, destination_blob_name: str):
    '''Uploads a file to the bucket.'''
    # bucket_name = 'your-bucket-name'
    # data = 'storage-object-content'
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    # blob.content_encoding = 'gzip'
    blob.upload_from_string(
        # data=gzip.compress(data=data, compresslevel=9),
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
