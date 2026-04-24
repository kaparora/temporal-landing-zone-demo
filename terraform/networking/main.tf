terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project   = "temporal-landing-zone-demo"
      Team      = var.team_name
      ManagedBy = "Temporal"
    }
  }
}

# ── Pick the first AZ in the region ──────────────────────────────────────────
data "aws_availability_zones" "available" {
  state = "available"
}

# ── VPC ───────────────────────────────────────────────────────────────────────
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "finco-${var.team_name}-vpc"
  }
}

# ── Public subnet ─────────────────────────────────────────────────────────────
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = {
    Name = "finco-${var.team_name}-public-subnet"
  }
}

# ── Internet gateway ──────────────────────────────────────────────────────────
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "finco-${var.team_name}-igw"
  }
}

# ── Public route table + default route ────────────────────────────────────────
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "finco-${var.team_name}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# ── Outputs (captured by the activity via `terraform output -json`) ───────────
output "vpc_id" {
  value       = aws_vpc.main.id
  description = "VPC ID for the team's landing zone."
}

output "subnet_cidr" {
  value       = aws_subnet.public.cidr_block
  description = "Primary public subnet CIDR block."
}

output "subnet_id" {
  value       = aws_subnet.public.id
  description = "Primary public subnet ID."
}

output "region" {
  value       = var.region
  description = "AWS region the landing zone was provisioned in."
}
