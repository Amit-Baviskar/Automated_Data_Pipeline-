# Automated Data Pipeline Using AWS (S3, Lambda, Glue, Step Functions, SNS)

----
## Index
   *  [Overview](#overview)
   *  [Tech Stack](#tech-stack) 

----
## Overview

 This project demonstrates a fully automated serverless data pipeline built on AWS to streamline the ingestion, transformation, and processing of daily CSV sales data. The pipeline eliminates manual intervention by using AWS Lambda to trigger workflows, AWS Glue for ETL operations, and AWS Step Functions for orchestration. Upon successful processing, the system sends a confirmation email to stakeholders using SNS.

----
## Architecture

![Image](https://github.com/user-attachments/assets/d9f3f38e-700e-467c-80db-b61e959e7966)


----
## Features

 * 📁 Automated file ingestion when CSV is uploaded to S3

 * 🔄 Orchestrated ETL flow using AWS Step Functions

 * 🧹 Data transformation and enrichment with AWS Glue

 * 📦 Converted to optimized Parquet format for long-term storage

 * 📧 Completion email notification via Amazon SNS

 * 🪵 Observability and logging with CloudWatch

----
## Tech Stack
  * AWS S3 – Storage for raw, preprocessed, and processed data

  * AWS Lambda – Trigger and control logic

  * AWS Glue – Crawling and ETL transformation jobs

  * AWS Step Functions – Workflow orchestration

  * AWS SNS – Notification service for job completion

  * AWS CloudWatch – Logging and monitoring
    
----
## Project Flow

 1 . Raw CSV is uploaded to s3://receipt-collector-uploads

 2. Lambda function is triggered automatically

 3. File is moved to s3://receipt-preprocessed

    AWS Step Function starts execution:

     * Glue Crawler updates schema

     * Glue ETL Job transforms the data (adds total_cost, extracts month/year, etc.)

     * Result is saved in Parquet format to s3://receipt-processed

     * Notification email is sent via SNS

Logs are captured in CloudWatch for monitoring

----

## Getting Started
  ## Prerequisites
----
 * AWS account with necessary IAM permissions

 * Pre-created S3 buckets:

      * receipt-collector-uploads

      * receipt-preprocessed

      * receipt-processed

  * Configured SNS topic and subscription
----
##  Setup Steps

 ## Step 1: Upload CSV to Raw S3 Bucket

  * Create S3 buckets:

     * csv-raw-zone-bucket/ → Input from user

     * csv-processed-input-bucket/ → Lambda-processed CSV

     * csv-transformed-output-bucket/ → Final output in Parquet

##  Step 2: Lambda Function (Triggered on CSV upload)

  Lambda Trigger:
       * Event: s3:ObjectCreated:* for csv-raw-zone-bucket/ 
       * Function copies or cleans file and moves to csv-processed-input-bucket/

      import boto3
      import json
      
      s3 = boto3.client('s3')
      sfn = boto3.client('stepfunctions')
      
      def lambda_handler(event, context):
          # Extract file details
          bucket = event['Records'][0]['s3']['bucket']['name']
          key = event['Records'][0]['s3']['object']['key']
    
    # Move to processed bucket
    copy_source = {'Bucket': bucket, 'Key': key}
    s3.copy_object(Bucket='csv-processed-bucket', Key=key, CopySource=copy_source)

    # Trigger Step Function
    sfn.start_execution(
        stateMachineArn='arn:aws:states:region:account-id:stateMachine:CsvProcessingPipeline',
        input=json.dumps({"filename": key})
    )

    return {"status": "Started Step Function"}



    

  ##  Step 3: Glue Crawler for Processed CSV  

  * Create Glue Database: csv_pipeline_db

  * Set Crawler source to s3://csv-processed-input-bucket/

  * Run the crawler → it will create a table in the Glue Catalog

 ## Step 4: Glue ETL Job

   Transformations to apply:
      * Drop null or bad rows
      * Convert date/time columns
      * Filter or rename columns
      * Save as Parquet in csv-transformed-output-bucket/

        
            import sys
            from pyspark.sql.functions import col, year, month, when
            from awsglue.transforms import *
            from awsglue.utils import getResolvedOptions
            from pyspark.context import SparkContext
            from awsglue.context import GlueContext
            from awsglue.job import Job
            
            # Initialize the Glue job
            args = getResolvedOptions(sys.argv, ['JOB_NAME'])
            sc = SparkContext()
            glueContext = GlueContext(sc)
            spark = glueContext.spark_session
            job = Job(glueContext)
            job.init(args['JOB_NAME'], args)
            
            # Load raw data from Glue Catalog
            input_dyf = glueContext.create_dynamic_frame.from_catalog(
                database="ecommerce_db",              # 👈 Your Glue DB name
                table_name="ecommerce_raw",           # 👈 Created by Glue Crawler
                transformation_ctx="input_dyf"
            )
            
            # Convert to Spark DataFrame
            df = input_dyf.toDF()
            
            # ✅ Transformations
            df = df.withColumn("TotalCost", col("Quantity") * col("UnitPrice"))
            df = df.withColumn("OrderDate", col("OrderDate").cast("timestamp"))
            df = df.withColumn("OrderMonth", month(col("OrderDate")))
            df = df.withColumn("OrderYear", year(col("OrderDate")))
            df = df.withColumn(
                "TransactionType",
                when(col("PaymentMethod").isin("Credit Card", "PayPal"), "Online")
                .when(col("PaymentMethod") == "Cash on Delivery", "Offline")
                .otherwise("Unknown")
            )
            
            # Convert back to DynamicFrame
            final_dyf = DynamicFrame.fromDF(df, glueContext, "final_dyf")
            
            # ✅ Write to S3 in Parquet format (partitioned by year and month)
            glueContext.write_dynamic_frame.from_options(
                frame=final_dyf,
                connection_type="s3",
                connection_options={
                    "path": "s3://ecommerce-final-bucket-10-07/",   # ✅ Final bucket
                    "partitionKeys": ["OrderYear", "OrderMonth"]
                },
                format="parquet",
                transformation_ctx="datasink"
            )
            
            # Commit the job
            job.commit()


----
 ## Step 5: Step Function 

   AWS Step Functions – Workflow orchestration 

   <img width="342" height="668" alt="Image" src="https://github.com/user-attachments/assets/ca666331-7fa1-4210-980b-9a1060a651a5" />


                   "Start Glue Crawler": {
                  "Type": "Task",
                  "Resource": "arn:aws:states:::aws-sdk:glue:startCrawler",
                  "Parameters": {
                    "Name": "ecommerce-crawler-10-07"
                  },
                  "Next": "Wait for Crawler"
                },
                
                "Wait for Crawler": {
                  "Type": "Wait",
                  "Seconds": 30,
                  "Next": "Check Crawler Status"
                },
                
                "Check Crawler Status": {
                  "Type": "Task",
                  "Resource": "arn:aws:states:::aws-sdk:glue:getCrawler",
                  "Parameters": {
                    "Name": "ecommerce-crawler-10-07"
                  },
                  "Next": "Is Crawler Still Running?"
                },
                
                "Is Crawler Still Running?": {
                  "Type": "Choice",
                  "Choices": [
                    {
                      "Variable": "$.Crawler.State",
                      "StringEquals": "READY",
                      "Next": "Run Glue ETL Job"
                    }
                  ],
                  "Default": "Wait for Crawler"
                
                }
                
                "Run Glue ETL Job": {
                  "Type": "Task",
                  "Resource": "arn:aws:states:::glue:startJobRun.sync",
                  "Parameters": {
                    "JobName": "ecommerce-etl-job-10-07"
                  },
                  "Next": "Send SNS Notification"
                },
                "Send SNS Notification": {
                  "Type": "Task",
                  "Resource": "arn:aws:states:::sns:publish",
                  "Parameters": {
                    "TopicArn": "arn:aws:sns:us-east-1:123456789012:etl-complete-topic",
                    "Subject": "ETL Job Complete",
                    "Message": "✅ Glue ETL Job has completed and your dashboard is ready."
                  },
                  "End": true
                }


    

     

----
##  Key Takeaways

 * Serverless architecture improves scalability and reduces maintenance

 * Fully automated ETL workflow with no human intervention

 * Email notifications enhance transparency for business stakeholders

 * Parquet format ensures efficient long-term storage and query readiness

----
##  Future Enhancements

 * Implement schema validation on incoming CSVs

 * Add retry logic and alerting for Glue job failures

 * Incorporate metadata tagging for better data cataloging

 * Add CI/CD deployment with AWS CDK or Terraform


----

