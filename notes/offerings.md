# Offerings Roadmap

## 1. Python Validation Library
- Validate data against models defined in .kye files

## 2. Python Integration Framework
- Define integration endpoints using kye queries
- Able to proxy endpoints for re-running against previously errored data or stored tests
- Register and use credentials from key stores
- CLI interface for running integrations and configuring accounts

_Need somewhere to define data transformations, or somehow let those be defined in existing
tools like prefect or dagster_

## 3. Local Integration Suite
- Localhost Web Interface for running/configuring locally defined integrations
- Register transformation code to be used elsewhere?

_Should we offer scheduling & alerting? Or leave those to other tools?_

## 4. Enterprise Integration Suite
- Hosted Web Interface
- Credentials & Data Cache stored in cloud
- Access control and account management (SAML Login?)