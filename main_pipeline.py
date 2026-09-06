import pandas as pd
from src.config import SOURCE_DIR, CLEANED_DIR
from src.cleaner import clean_orders, clean_reviews, clean_items, clean_geolocation, clean_products

def run_cleaning_pipeline():
    cleaning_map = {
        'olist_orders_dataset': clean_orders,
        'olist_order_reviews_dataset': clean_reviews,
        'olist_order_items_dataset': clean_items,
        'olist_geolocation_dataset': clean_geolocation,
        'olist_products_dataset': clean_products,
        'olist_customers_dataset': lambda df: df, 
        'olist_sellers_dataset': lambda df: df,
        'olist_order_payments_dataset': lambda df: df,
        'product_category_name_translation': lambda df: df
    }

    print(f"Scanning for CSV files in {SOURCE_DIR}...")
    
    for file_path in SOURCE_DIR.glob('*.csv'):
        file_name = file_path.stem
        print(f"Processing: {file_name}.csv")
        
        df = pd.read_csv(file_path)
        
        for key, clean_func in cleaning_map.items():
            if key in file_name:
                df = clean_func(df)
                break
                
        df = df.drop_duplicates()
        
        output_path = CLEANED_DIR / f"cleaned_{file_name}.csv"
        df.to_csv(output_path, index=False)
        print(f"Saved: {output_path}")

if __name__ == "__main__":
    print("Starting ETL Pipeline...")
    run_cleaning_pipeline()
    print("Data cleaning complete.")