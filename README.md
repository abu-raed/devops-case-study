# devops-case-study
for demonstration on aws# DevOps Platform Engineering Case Study

**Author:** Rizwan Javid

---

# Overview

This project demonstrates a production-oriented Kubernetes platform built entirely on AWS from a greenfield environment. The solution showcases end-to-end platform engineering practices including:

* Kubernetes provisioning using **kops**
* Application packaging with **Helm**
* Environment configuration management using **Ansible**
* Containerized application deployment on Kubernetes
* Autoscaling using **HPA** and **Cluster Autoscaler**
* Automated file archiving to **Amazon S3 with Glacier lifecycle policies**
* Secure and repeatable infrastructure deployment

---

# Technology Stack

| Category                 | Technologies          |
| ------------------------ | --------------------- |
| Cloud                    | AWS                   |
| Container Platform       | Kubernetes 1.35, kops |
| Packaging                | Helm                  |
| Configuration Management | Ansible  Not tested             |
| Container Runtime        | Docker                |
| Application              | Python Flask, Nginx   |
| Storage                  | Amazon S3, Glacier    |
| Registry                 | Amazon ECR            |
| Networking               | AWS NLB               |

---

# Solution Architecture

```
Internet
    │
    ▼
AWS Network Load Balancer
    │
    ▼
Kubernetes Service (LoadBalancer)
    │
    ▼
┌───────────────────────────────┐
│          Application Pod      │
│                               │
│  ┌─────────┐   ┌───────────┐   │
│  │ Nginx   │◄──► Flask App │   │
│  └─────────┘   └───────────┘   │
│          Shared emptyDir       │
└───────────────────────────────┘
    │
    ▼
Amazon S3
    │
    ▼
Glacier Lifecycle Policy
```

![Architecture Flow](screenshots/flow.png "Architecture Diagram")
---

# Kubernetes Cluster Design

The Kubernetes platform is deployed using **kops** and follows high-availability principles:

* Multi-instance-group architecture
* Combination of on-demand and spot worker nodes
* Cluster Autoscaler with ASG auto-discovery
* Private worker nodes
* Highly available control plane across multiple Availability Zones
* Metrics Server integration for autoscaling

---

# Application Design

The application uses the **Sidecar Pattern**:

### Components

#### Flask Application

* Processes uploaded CSV files
* Displays processed data
* Uploads files to Amazon S3
* Applies Glacier lifecycle policies

#### Nginx Sidecar

* Serves static content
* Reverse proxies requests to Flask
* Handles health checks

#### Shared Storage

An `emptyDir` volume is used to share static assets between containers, satisfying the requirement of avoiding NFS-based storage.

---

# Autoscaling

## Horizontal Pod Autoscaler (HPA)

The application automatically scales based on:

* CPU utilization
* Memory utilization
* Minimum and maximum replica boundaries
* Controlled scale-up and scale-down policies

## Cluster Autoscaler

The cluster automatically:

* Adds worker nodes when pods become unschedulable
* Supports scale-from-zero node groups
* Optimizes utilization across node pools
* Handles dynamic workload demand

---

# Helm-Based Deployment

All Kubernetes resources are packaged into a reusable Helm chart.

### Helm Components

* Namespace
* ConfigMaps
* Secrets
* Deployment
* Service
* HorizontalPodAutoscaler
* Nginx configuration
* Application configuration

### Deployment

```bash
helm install webapp ./helm/webapp-chart
```

Benefits:

* Versioned releases
* Rollback support
* Environment overrides
* Repeatable deployments

---

# Configuration Management with Ansible

Ansible is used to manage environment-specific configurations independently from deployment topology.

Examples:

* Environment variables
* Application settings
* Nginx configuration
* Feature flags
* Environment-specific endpoints

This approach allows the same Helm chart to be promoted across environments with minimal changes.

---

# Storage and Archiving

Processed CSV files are automatically:

1. Uploaded to Amazon S3
2. Assigned lifecycle policies
3. Archived to Glacier storage classes

The lifecycle process is idempotent and can be executed repeatedly without affecting existing configurations.

---

# Security Considerations

Implemented security practices include:

* Least-privilege IAM policies
* Private worker nodes
* Encrypted S3 storage
* Kubernetes Secrets for sensitive data
* Private container registry (Amazon ECR)
* Scoped permissions for Cluster Autoscaler
* Recommendation for IAM Roles for Service Accounts (IRSA)

---

# Deployment Workflow

```text
AWS CLI Configuration
          ↓
Create kops Cluster
          ↓
Install Metrics Server
          ↓
Deploy Cluster Autoscaler
          ↓
Build & Push Docker Image
          ↓
Deploy Helm Chart
          ↓
Apply Ansible Configuration
          ↓
Verify Application & S3 Archiving
```

---

# Key Engineering Decisions

* Kubernetes provisioned using **kops** for infrastructure control.
* **Helm** chosen for versioned and repeatable deployments.
* **Ansible** used to separate configuration from deployment topology.
* **Nginx Sidecar Pattern** adopted for efficient static content delivery.
* **emptyDir** selected for lightweight shared storage.
* Combined use of **HPA** and **Cluster Autoscaler** for elastic scaling.
* Security-first approach with private networking and least-privilege access.

---

# Project Outcome

This project demonstrates practical experience in:

* Platform Engineering
* Kubernetes Administration
* DevSecOps Practices
* Infrastructure Automation
* GitOps and Deployment Automation
* Cloud-Native Application Delivery
* Production-Grade Kubernetes Architecture
* Secure and Scalable AWS Deployments

