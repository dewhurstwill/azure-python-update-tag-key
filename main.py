# Importing packages
import requests, json, uuid

# Script settings & parameters
defaults_check = False
enable_debug = False
include_resource_groups = True
exclude_resources = False
# Batch mode is less stable but useful 
# when you need to limit the number of api calls
run_in_batch_mode = False

# Setting Validation
if not defaults_check:
    message = 'At the top of the file there is a number of variables that can be set to change how it runs'
    print('--' + ('-' * len(message)))
    print()
    print('Edit this file to access settings')
    print(message)
    print('To stop this message from displaying set the variable defaults_check to True')
    print()
    print('--' + ('-' * len(message)))
    exit()

if enable_debug:
    message = 'You are running in debug mode will result in more logs outputing to the console'
    print('--' + ('-' * len(message)))
    print()
    print(message)
    print()
    print('--' + ('-' * len(message)))
    print()
    continue_q = input('Are you sure you want to continue (input will only continue with yes in all lowercase): ')
    if continue_q != 'yes':
        print('Exiting...')
        exit()
    else:
        print('Stating...')
        print('')
else:
    print('Stating...')
    print('')
    
if not include_resource_groups and exclude_resources:
    print('You must include resources or resource groups for the script to do something')
    exit()

print('We will now collect some details...')
print('')

# Inputs from user
tenant_id = input('Tenant ID: ')
if len(tenant_id) < 1:
    print('Tenant ID is required for this script')
    print('Exiting...')
    exit()
client_id = input('Client ID: ')
if len(client_id) < 1:
    print('Client ID is required for this script')
    print('Exiting...')
    exit()
client_secret = input('Client Secret: ')
if len(client_secret) < 1:
    print('Client Secret is required for this script')
    print('Exiting...')
    exit()
old_key = input('Old key: ')#'Owner'
if len(old_key) < 1 and len(old_key) < 16:
    print('old_key must be at least 1 character but less than 16 characters')
    print('Exiting...')
    exit()
new_key = input('New key: ')#'Owner2'
if len(new_key) < 1 and len(new_key) < 16:
    print('new_key must be at least 1 character but less than 16 characters')
    print('Exiting...')
    exit()

# Global Variable
base_url = 'https://management.azure.com'

# Helper Functions
## Authenticate against azure function
def authenticate(tenant_id, client_id, client_secret):
    auth_url = 'https://login.microsoftonline.com/' + tenant_id + '/oauth2/token'
    auth_payload = 'grant_type=client_credentials&resource=https%3A%2F%2Fmanagement.azure.com&client_id=' + client_id + '&client_secret=' + client_secret
    print('Authenticating')
    auth_response = requests.request('POST', auth_url, headers={ 
        'Content-Type': 'application/x-www-form-urlencoded'
    }, data=auth_payload)
    auth_json_response = json.loads(auth_response.text)
    auth_token = auth_json_response['token_type'] + ' ' + auth_json_response['access_token']
    if 'Bearer ' in auth_token:
        print('Authenticated')
    return auth_token

## Get subscriptions from azure
def getSubscriptions(auth_token):
    subscriptions_url = base_url + '/subscriptions?api-version=2020-01-01'
    print('Checking what subscriptions you have access to')
    all_subscriptions = []
    subscriptions_response = requests.request('GET', subscriptions_url, headers={
        'Authorization': auth_token
    }, data={})
    for subscription in json.loads(subscriptions_response.text)['value']:
        all_subscriptions.append(subscription['displayName'])
    print(str(len(all_subscriptions)) + 'subscription(s) found: \n' + ', '.join(all_subscriptions))
    print('')
    print('')
    return subscriptions_response.text

## Get resources from azure 
def getResources(subscription_id, getGroups, auth_token):
    url = base_url + '/subscriptions/' + subscription_id + '/resource'
    if getGroups:
        url = url + 'groups'
    else:
        url = url + 's'
    url = url + '?api-version=2020-06-01'
    resources_response = requests.request('GET', url, headers={
        'Authorization': auth_token
    }, data={})
    return resources_response.text

## Update tags
def updateTags(resourceId, tags, auth_token):
    resource_url = base_url + resourceId + '/providers/Microsoft.Resources/tags/default?api-version=2019-10-01'

    data = {
        'operation': 'replace',
        'properties': {
            'tags': tags
        }
    }
    body = json.dumps(data)
    tag_update_response = requests.request('PATCH', resource_url, headers={
        'Content-Type': 'application/json',
        'Authorization': auth_token
    }, data=body)
    return tag_update_response.text

## Run requests in batches
def batchRequests(request, auth_token):
    batch_url = base_url + '/batch?api-version=2021-01-01'
    body = json.dumps(request)
    batch_response = requests.request('POST', batch_url, headers={
        'Content-Type': 'application/json',
        'Authorization': auth_token
    }, data=body)
    return batch_response.text

print('')
print('')
print('')
auth_token = authenticate(tenant_id, client_id, client_secret)
subscriptions_response = getSubscriptions(auth_token);
subscriptions_json_response = json.loads(subscriptions_response)
batch_requests = []
for subscription in subscriptions_json_response['value']:
    subscription_id = subscription['subscriptionId']
    print('Getting resources from ' + subscription['displayName'] + ' - ' + subscription_id)
    print('')
    resource_response = getResources(subscription_id, exclude_resources, auth_token)
    resource_json_response = json.loads(resource_response)
    if not exclude_resources and include_resource_groups:
        print('Getting resource groups from ' + subscription['displayName'] + ' - ' + subscription_id)
        print('')
        resource_group_response = getResources(subscription_id, True, auth_token)
        resource_group_json_response = json.loads(resource_group_response)
        resource_json_response['value'] = resource_json_response['value'] + resource_group_json_response['value']

    for resource in resource_json_response['value']:
        if resource and 'tags' in resource and old_key in resource['tags']:
            tags = resource['tags']
            tags[new_key] = tags[old_key]
            del tags[old_key]
            if run_in_batch_mode:
                batch_requests.append({
                    'content': {
                        'tags': tags
                    },
                    'httpMethod': 'PATCH',
                    'name': str(uuid.uuid4()),
                    'requestHeaderDetails': { 
                        'commandName': 'Microsoft_Azure_Storage.ArmTags.patchResourceTags'
                    },
                    'url': resource['id'] + '?api-version=2017-10-01'
                })
            else:
                batch_requests.append({
                    'id': resource['id'],
                    'tags': tags
                })
    
if run_in_batch_mode:
    if enable_debug:
        print('Number of requests to make: ' + str(requests_to_process))
        print('All Requests:')
        print(batch_requests)

    requests_to_process = len(batch_requests)
    current_batch = batch_requests
    request_start_index = 0
    request_end_index = 19
    batch_number = 1

    while requests_to_process > 0:
        print('Starting batch ' + str(batch_number))
        if requests_to_process > 20:
            current_batch = batch_requests[request_start_index:request_end_index]
            request_start_index = request_start_index + 20
            request_end_index = request_end_index + 20
        else:
            current_batch = batch_requests[request_start_index:len(batch_requests)]
        requests_to_process = requests_to_process - 20
        batch_number = batch_number + 1
        print('Running batch ' + str(batch_number))
        batch_response = batchRequests({
            'requests': current_batch
        }, auth_token)
        print('Batch ' + str(batch_number) + ' finished')
        print('')
        if enable_debug:
            print(batch_response)
else:
    print('Running')
    for resource in batch_requests:
        resource_json = json.loads(resource)
        updateTags(resource_json['id'], resource_json['tags'])
    message = ' resources'
    if include_resource_groups:
        message = message + '/resource groups'
    print(str(len(batch_requests)) + message + ' have been tagged.')

print('')
print('--------')
print('Complete')
print('--------')