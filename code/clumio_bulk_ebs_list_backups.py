# Copyright 2024, Clumio Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from botocore.exceptions import ClientError
import boto3
import json
from clumio_sdk_v13 import DynamoDBBackupList, RestoreDDN, ClumioConnectAccount, AWSOrgAccount, ListEC2Instance, \
    EnvironmentId, RestoreEC2, EC2BackupList, EBSBackupList, RestoreEBS, OnDemandBackupEC2, RetrieveTask


def lambda_handler(events, context):
    bear = events.get('bear', None)
    source_account = events.get('source_account', None)
    source_region = events.get('source_region', None)
    search_tag_key = events.get('search_tag_key', None)
    search_tag_value = events.get('search_tag_value', None)
    search_direction = events.get('search_direction', None)
    start_search_day_offset_input = events.get('start_search_day_offset', 0)
    end_search_day_offset_input = events.get('end_search_day_offset', 10)
    target = events.get('target',{})
    debug_input = events.get('debug', 0)

    # If clumio bearer token is not passed as an input read it from the AWS secret
    if not bear:
        bearer_secret = "clumio/token/bulk_restore"
        secretsmanager = boto3.client('secretsmanager')
        try:
            secret_value = secretsmanager.get_secret_value(SecretId=bearer_secret)
            secret_dict = json.loads(secret_value['SecretString'])
            # username = secret_dict.get('username', None)
            bear = secret_dict.get('token', None)
        except ClientError as e:
            error = e.response['Error']['Code']
            error_msg = f"Read secret failed - {error}"
            payload = error_msg
            return {"status": 411, "msg": error_msg}

    # Validate inputs
    try:
        start_search_day_offset = int(start_search_day_offset_input)
        end_search_day_offset = int(end_search_day_offset_input)
        debug = int(debug_input)
    except ValueError as e:
        error = f"invalid task id: {e}"
        return {"status": 401, "records": [], "msg": f"failed {error}"}


    # Initiate API and configure
    ebs_backup_list_api = EBSBackupList()
    ebs_backup_list_api.set_token(bear)
    ebs_backup_list_api.set_debug(debug)

    # Set search parameters
    if search_tag_key and search_tag_value:
        ebs_backup_list_api.ebs_search_by_tag(search_tag_key, search_tag_value)
    if search_direction == 'forwards':
        ebs_backup_list_api.set_search_forwards_from_offset(end_search_day_offset)
    elif search_direction == 'backwards':
        ebs_backup_list_api.set_search_backwards_from_offset(start_search_day_offset, end_search_day_offset)

    ebs_backup_list_api.set_aws_account_id(source_account)
    ebs_backup_list_api.set_aws_region(source_region)

    # Run search
    ebs_backup_list_api.run_all()

    # Parse and return results
    result_dict = ebs_backup_list_api.ebs_parse_results("restore")
    ebs_backup_records = result_dict.get("records", [])
    if len(ebs_backup_records) == 0:
        return {"status": 207, "records": [], "target": target,"msg": "empty set"}
    else:
        return {"status": 200, "records": ebs_backup_records, "target": target, "msg": "completed"}