from google_auth_oauthlib.flow import InstalledAppFlow
import os

GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.send']

flow = InstalledAppFlow.from_client_secrets_file(
    'gmail_credentials.json',
    scopes=GMAIL_SCOPES
)
creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')

# Save token for future use
with open('token.json', 'w') as token_file:
    token_file.write(creds.to_json())
