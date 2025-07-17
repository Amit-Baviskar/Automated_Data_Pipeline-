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