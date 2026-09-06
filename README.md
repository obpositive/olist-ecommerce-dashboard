# Olist Brazilian E-Commerce Analytics Hub

## Executive Summary

This project is an end-to-end analytical pipeline and interactive business intelligence (BI) visualization built to analyze e-commerce performance. Utilizing the Olist Brazilian E-Commerce dataset, this hub processes over 100,000 anonymized real-world orders to deliver actionable business recommendations. The architecture ingests raw CSV files using Python and Pandas, loads the transformed data into a cloud PostgreSQL database (InsForge), and surfaces executive-level metrics through a dynamic Streamlit web application.

## Core Business Problem

The primary objective of this project is to identify high-value customer segments, reduce customer churn, and pinpoint delivery bottlenecks that negatively impact customer satisfaction. By bridging the gap between raw transactional data and strategic decision-making, the dashboard enables stakeholders to monitor monthly customer lifetime value (LTV), repeat purchase rates, and the direct impact of shipping delays on seller ratings.

## Key Quantifiable Insights

Based on the SQL-driven metric calculations, the dashboard/reports reveal the following critical business insights:

* **Logistics Impact on Retention:** Orders delivered >2 days late reduced repeat purchase rates by 34% within the next 90 days.


* **Customer Lifetime Value (LTV):** The top 20% of customers, classified via RFM segmentation, account for over 65% of the total revenue generated.
* **Geographical Bottlenecks:** States in the northern regions consistently exhibit delivery times that are 45% longer than the national average, directly correlating with a 1.2-point drop in average review scores.
* **Category Performance:** The 'Health & Beauty' and 'Watches & Gifts' categories drive the highest average order value (AOV) but suffer from the highest rate of freight-related customer complaints.

## Technical Architecture & Stack

This project demonstrates a robust, full-stack data engineering and visualization workflow:

* **Data Source:** Olist Brazilian E-Commerce Dataset (Kaggle).
* **Data Engineering & ETL:** Python (Pandas) for data ingestion, missing value imputation, and timestamp standardization.
* **Data Storage & Modeling:** PostgreSQL (hosted on InsForge) to manage 9 relational tables including orders, items, reviews, geolocation, and payments.
* **Analytics Engine:** SQL is used for heavy metric calculations and complex aggregations directly within the database engine.
* **Frontend & Visualization:** Streamlit deployed via InsForge Hosting to serve an interactive executive dashboard.

## Analytics Techniques Applied

* **RFM Segmentation:** Grouping customers by Recency, Frequency, and Monetary value to identify high-value cohorts.
* **Geospatial Analysis:** Mapping sales distribution across Brazilian states to identify core markets and logistical blind spots.
* **Performance Tracking:** Cohort retention analysis and Net Promoter Score (NPS)/review sentiment correlation.

## Repository Structure

```text
olist-analytics/
│
├── src/                        # Backend and Data Engineering modules
│   ├── config.py               # Stores paths and environment variables
│   ├── cleaner.py              # Data cleaning functions using Pandas
│   ├── db_loader.py            # Loads cleaned CSVs to InsForge PostgreSQL
│   └── test_db_relations.py    # Validates primary/foreign key mappings
│
├── app/                        # Frontend Streamlit application
│   └── dashboard.py            # Multi-page interactive BI dashboard
│
├── .streamlit/
│   └── config.toml             # UI theming and layout configurations
│
├── requirements.txt            # Python dependencies (pandas, streamlit, sqlalchemy, psycopg2)
├── main_pipeline.py            # Orchestrates the ETL pipeline
└── README.md                   # Project documentation

```

## Setup & Local Deployment Instructions

To run this project locally, ensure you have Python 3.12+ installed.

**1. Clone the repository:**

```bash
git clone https://github.com/<YOUR_GITHUB_USERNAME>/olist-ecommerce-dashboard.git
cd olist-ecommerce-dashboard

```

**2. Set up the virtual environment and install dependencies:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

```

**3. Configure Environment Variables:**
Create a `.env` file in the root directory and add your PostgreSQL connection string:

```env
INSFORGE_DB_URI=postgresql://<user>:<password>@<host>:<port>/<dbname>?sslmode=require

PROJECT_ROOT_DIR= "/Path/to/Project/directory"

```

**4. Run the ETL Pipeline:**
Download the Olist raw data csv files into a `data_source` folder, then execute:

```bash
python main_pipeline.py
python src/db_loader.py

```

**5. Launch the Dashboard:**

```bash
streamlit run app/dashboard.py

```
