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