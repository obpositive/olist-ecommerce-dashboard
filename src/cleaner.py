import pandas as pd

def clean_orders(df):
    time_columns = [
        'order_purchase_timestamp', 'order_approved_at', 
        'order_delivered_carrier_date', 'order_delivered_customer_date', 
        'order_estimated_delivery_date'
    ]
    for col in time_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df

def clean_reviews(df):
    time_columns = ['review_creation_date', 'review_answer_timestamp']
    for col in time_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    if 'review_comment_title' in df.columns:
        df['review_comment_title'] = df['review_comment_title'].fillna('')
    if 'review_comment_message' in df.columns:
        df['review_comment_message'] = df['review_comment_message'].fillna('')
    return df

def clean_items(df):
    if 'shipping_limit_date' in df.columns:
        df['shipping_limit_date'] = pd.to_datetime(df['shipping_limit_date'], errors='coerce')
    return df

def clean_geolocation(df):
    return df.drop_duplicates(subset=['geolocation_zip_code_prefix', 'geolocation_lat', 'geolocation_lng'])

def clean_products(df):
    if 'product_category_name' in df.columns:
        df['product_category_name'] = df['product_category_name'].fillna('unknown')
    num_cols = [
        'product_name_lenght', 'product_description_lenght', 
        'product_photos_qty', 'product_weight_g', 
        'product_length_cm', 'product_height_cm', 'product_width_cm'
    ]
    for col in num_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0)
    return df