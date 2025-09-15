"""
Deployment script for the IAM Role Vending Machine.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def run_command(command: str, cwd: str = None) -> bool:
    """Run a shell command and return success status."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"✓ {command}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {command}")
        print(f"Error: {e.stderr}")
        return False


def create_lambda_packages():
    """Create Lambda deployment packages."""
    print("Creating Lambda deployment packages...")
    
    # Create role vendor package
    if not run_command("pip install -r requirements.txt -t lambda_functions/"):
        return False
    
    # Copy source code to lambda_functions
    src_path = Path("src/iam_temprole_creator")
    lambda_path = Path("lambda_functions")
    
    if src_path.exists():
        shutil.copytree(src_path, lambda_path / "iam_temprole_creator", dirs_exist_ok=True)
    
    # Create zip files
    if not run_command("cd lambda_functions && zip -r role_vendor.zip . -x '*.pyc' '__pycache__/*'", cwd="."):
        return False
    
    if not run_command("cd lambda_functions && zip -r cleanup.zip cleanup_handler.py iam_temprole_creator/", cwd="."):
        return False
    
    return True


def deploy_infrastructure():
    """Deploy AWS infrastructure using Terraform."""
    print("Deploying AWS infrastructure...")
    
    # Initialize Terraform
    if not run_command("terraform init", cwd="infrastructure"):
        return False
    
    # Plan deployment
    if not run_command("terraform plan -out=tfplan", cwd="infrastructure"):
        return False
    
    # Apply deployment
    if not run_command("terraform apply tfplan", cwd="infrastructure"):
        return False
    
    return True


def upload_policy_templates():
    """Upload policy templates to S3."""
    print("Uploading policy templates...")
    
    # Get S3 bucket name from Terraform output
    try:
        result = subprocess.run(
            "terraform output -raw policy_templates_bucket",
            shell=True,
            cwd="infrastructure",
            capture_output=True,
            text=True,
            check=True
        )
        bucket_name = result.stdout.strip()
    except subprocess.CalledProcessError:
        print("Error: Could not get S3 bucket name from Terraform output")
        return False
    
    # Upload templates
    for template_file in Path("policy_templates").glob("*.json"):
        if not run_command(f"aws s3 cp {template_file} s3://{bucket_name}/templates/{template_file.name}"):
            return False
    
    return True


def install_cli():
    """Install CLI tool."""
    print("Installing CLI tool...")
    
    if not run_command("pip install -e ."):
        return False
    
    return True


def main():
    """Main deployment function."""
    print("🚀 Deploying IAM Role Vending Machine")
    print("=" * 50)
    
    # Check prerequisites
    required_commands = ["terraform", "aws", "pip"]
    for cmd in required_commands:
        if not shutil.which(cmd):
            print(f"Error: {cmd} command not found. Please install it first.")
            sys.exit(1)
    
    # Create Lambda packages
    if not create_lambda_packages():
        print("Error: Failed to create Lambda packages")
        sys.exit(1)
    
    # Deploy infrastructure
    if not deploy_infrastructure():
        print("Error: Failed to deploy infrastructure")
        sys.exit(1)
    
    # Upload policy templates
    if not upload_policy_templates():
        print("Error: Failed to upload policy templates")
        sys.exit(1)
    
    # Install CLI
    if not install_cli():
        print("Error: Failed to install CLI tool")
        sys.exit(1)
    
    print("\n✅ Deployment completed successfully!")
    print("\nNext steps:")
    print("1. Configure your AWS credentials")
    print("2. Test the CLI: iam-role-vendor --help")
    print("3. Request a role: iam-role-vendor request-role --help")


if __name__ == "__main__":
    main()
