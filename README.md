# multi-cloud-security-automation

Working files for Steps 3–4 of the DevSecOps portfolio plan: IaC network
foundations in Terraform (AWS + Azure) and a Python cross-cloud MFA
compliance auditor. Step 5 (architecture diagram + full case-study README)
is intentionally not built yet — see the review notes for why.

## Layout

```
terraform/
  aws-vpc/            # VPC, public+private subnets across AZs, NAT, IGW
  azure-hub-spoke/     # Hub VNet + spoke VNet, peered, NSGs on each subnet
scripts/
  mfa_compliance_report.py   # AWS IAM + Entra ID MFA audit -> CSV
  requirements.txt
  .env.example
```

## Terraform — quick start

Neither module has been `terraform apply`'d or even `terraform validate`'d
against real provider plugins (this environment couldn't reach
releases.hashicorp.com to install the CLI) — only syntax-checked offline.
Validate for real before trusting it against a live account:

```bash
cd terraform/aws-vpc      # or terraform/azure-hub-spoke
cp terraform.tfvars.example terraform.tfvars   # edit values
terraform init
terraform validate
terraform plan
```

## Python script — quick start

```bash
cd scripts
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in and export, or use direnv/dotenv
python3 mfa_compliance_report.py --aws --azure --output mfa_report.csv
```

The Azure side needs an app registration with `UserAuthenticationMethod.Read.All`
and `User.Read.All` **application** permissions, admin-consented — that's a
tenant-level grant, so budget time for that step if you're auditing a real
tenant instead of a lab one.
