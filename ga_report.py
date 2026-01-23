import os
import re
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from google.cloud import storage, exceptions
from google.analytics.data_v1beta import BetaAnalyticsDataAsyncClient
from google.analytics.data_v1beta.types import (
    DateRange, 
    Dimension, 
    Metric, 
    RunReportRequest
)
from gql_client import GraphQLClient
from gql_queries import GET_POSTS_BY_SLUGS



def format_post_data(post):
    data = post.copy()
    data.pop('exclusive', None)
    if 'heroImage' in data and data['heroImage']:
        resized = data['heroImage'].get('resized')
        if resized:
            data['heroImage'] = {
                'urlTinySized': resized.get('w480'),
                'urlMobileSized': resized.get('w800')
            }
        else:
            data['heroImage'] = None
    return data


async def get_article_async(response):
    graphql_client = GraphQLClient()
    gql_client = await graphql_client.get_authenticated_client()

    target_slugs = []
    id_bucket = []
    exclusive = ["aboutus", "ad-sales", "adsales", "biography", "complaint", "faq", "press-self-regulation", "privacy", "standards", "webauthorization"]
    
    for row in response.rows:
        uri = row.dimension_values[1].value
        id_match = re.match('/story/([\w-]+)', uri)
        if id_match:
            post_id = id_match.group(1)
            if post_id in id_bucket:
                continue
            if post_id and post_id[:3] != 'mm-' and post_id not in exclusive:
                target_slugs.append(post_id)
                id_bucket.append(post_id)

    if not target_slugs:
        return {'articles': [], 'yt': []}

    # 執行批次查詢
    try:
        async with gql_client as session:
            result = await session.execute(GET_POSTS_BY_SLUGS, variable_values={"slugs": target_slugs})
            posts_from_db = result.get('posts', [])
    except Exception as e:
        print(f"Batch GraphQL query failed: {e}")
        return {'articles': [], 'yt': []}

    # 建立對照表並排序
    posts_map = {p['slug']: p for p in posts_from_db}

    report = {'articles': [], 'yt': []}
    yt_id = [] 
    rows = 0
    yt_rows = 0

    for slug in target_slugs:
        post = posts_map.get(slug)
        if not post:
            continue
            
        rows += 1
        if rows <= 30:
            report['articles'].append(format_post_data(post))
            
        if post.get('source') == 'yt' and post['id'] not in yt_id:
            yt_id.append(post['id'])
            report['yt'].append(format_post_data(post))
            yt_rows += 1
            
        if rows > 30 and yt_rows > 10:
            break

    return report


async def popular_report(property_id):
    try:    
        client = BetaAnalyticsDataAsyncClient()
    except Exception as e:
        print(f"Failed to initialize GA client: {e}")
        return "failed"
    tz = ZoneInfo("Asia/Taipei")
    current_time = datetime.now(tz)
    start_date = (current_time - timedelta(days=2)).strftime('%Y-%m-%d')
    end_date = current_time.strftime('%Y-%m-%d')

    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="pageTitle"), Dimension(name="pagePath")],
        metrics=[Metric(name="screenPageViews")],
        date_ranges=[DateRange(start_date=start_date, end_date="today")],
    )

    try:
        response = await client.run_report(request)
    except Exception as e:
        print(f"Failed to get GA report: {e}")
        return "failed"

    report_data = await get_article_async(response)
    
    gcs_path = os.environ.get('GCS_PATH', '')
    bucket_name = os.environ.get('BUCKET', '')
    gen_time_str = current_time.strftime('%Y-%m-%d %H:%M')

    popular_list = { 
        "report": report_data['articles'], 
        "start_date": start_date, 
        "end_date": end_date, 
        "generate_time": gen_time_str
    }
    popular_video = { 
        "report": report_data['yt'], 
        "start_date": start_date, 
        "end_date": end_date, 
        "generate_time": gen_time_str
    }

    upload_data(bucket_name, json.dumps(popular_list, ensure_ascii=False).encode('utf8'), 'application/json', gcs_path + 'popularlist.json')
    upload_data(bucket_name, json.dumps(popular_video, ensure_ascii=False).encode('utf8'), 'application/json', gcs_path + 'popular-videonews-list.json')
    
    return "Ok"


def upload_data(bucket_name, data, content_type, destination_blob_name):
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_string(data=data, content_type=content_type)
        blob.content_language = 'zh'
        blob.cache_control = 'max-age=300,public'
        blob.patch()
        print(f"Successfully uploaded: {destination_blob_name}")
        return True
    except exceptions.GoogleCloudError as e:
        print(f"Failed to upload {destination_blob_name} to GCS: {e}")
    except Exception as e:
        print(f"Unexpected error during GCS upload: {e}")
    return False