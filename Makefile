

.PHONY: extract-dependencies deploy-cloud-function deploy-scheduler-job deploy

# ----- personal settings -----
GCP_PROJECT_ID="ssx999-hedge"
GCP_SERVICE_ACCOUNT="ssx999-hedge-account@ssx999-hedge.iam.gserviceaccount.com"
GCP_BUCKET="ssx999-hedge-b1"
GCP_REGION="europe-west6"
SCHEDULE="*/1 * * * *"
# ----- ----------------- -----

FUNCTION_NAME="hedger"
TOPIC_NAME="hedger_topic"
CODE_ENTRYPOINT=main

JOB_NAME="hedger_job"
MESSAGE_BODY="Run successful"

update-requirements:
	poetry export --without-hashes -f requirements.txt --output requirements.txt

deploy-cloud-function: update-requirements
	gcloud beta functions deploy $(FUNCTION_NAME) --service-account=$(GCP_SERVICE_ACCOUNT) --entry-point $(CODE_ENTRYPOINT) --runtime python38 --trigger-resource $(TOPIC_NAME) --trigger-event google.pubsub.topic.publish --timeout 540s --project=$(GCP_PROJECT_ID) --region=$(GCP_REGION) --set-env-vars IS_LOCAL=false --set-env-vars GCP_BUCKET=$(GCP_BUCKET) --retry

deploy-scheduler-job:
	gcloud beta scheduler jobs create pubsub $(JOB_NAME) --schedule $(SCHEDULE) --topic $(TOPIC_NAME) --message-body $(MESSAGE_BODY) --project=$(GCP_PROJECT_ID)

deploy: deploy-cloud-function deploy-scheduler-job
	echo "-- Deployed --"


.PHONY: delete-cloud-function delete-scheduler-job delete


delete-cloud-function:
	gcloud beta functions delete $(FUNCTION_NAME) --project=$(GCP_PROJECT_ID) --region=$(GCP_REGION)

delete-scheduler-job:
	gcloud beta scheduler jobs delete $(JOB_NAME) --project=$(GCP_PROJECT_ID)

delete: delete-cloud-function delete-scheduler-job


.PHONY: run-local


run-local: export IS_LOCAL=true
run-local:
	poetry run python main.py


run-bucket: export IS_LOCAL=false
run-bucket:
	GCP_BUCKET=$(GCP_BUCKET) poetry run python main.py
