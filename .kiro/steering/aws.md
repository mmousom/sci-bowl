# AWS Environment Configuration

## Python Virtual Environment
- This project uses a virtual environment at `venv/` (Python 3.13.2).
- Always use `venv/bin/python` or `venv/bin/pip` for running scripts and installing packages.
- Activate with: `source venv/bin/activate`
- All dependencies are pinned in `requirements.txt` and already installed in the venv.



## Profile
- Always use the AWS profile `onasmmon` for all AWS operations in this project.
- Set `AWS_PROFILE=onasmmon` when running AWS CLI commands or SDK-based scripts.

## Usage Examples
- CLI: `aws --profile onasmmon <command>`
- CDK: `cdk --profile onasmmon <command>`
- Environment variable: `export AWS_PROFILE=onasmmon`

## SDK Configuration
- When initializing AWS SDK clients (boto3, AWS SDK for JS/TS, etc.), explicitly pass the profile name `onasmmon` rather than relying on the default credential chain.
- Example (Python/boto3): `session = boto3.Session(profile_name='onasmmon')`
- Example (TypeScript): `const credentials = fromIni({ profile: 'onasmmon' })`

## Notes
- Never hardcode AWS credentials (access key ID, secret access key) in code or config files.
- Use the `onasmmon` profile for both local development and any infrastructure-as-code deployments scoped to this project.
