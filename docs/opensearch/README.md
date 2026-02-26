# OpenSearch Operator Documentation

This directory contains comprehensive documentation for the OpenSearch vector database operator.

## Documentation Files

### [DOCKER_SETUP.md](DOCKER_SETUP.md)
Guide for running OpenSearch locally with Docker for development and testing.

**Contents:**
- Docker Compose setup
- Quick start instructions
- OpenSearch Dashboards access
- Configuration options
- Troubleshooting
- Data persistence

### [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md)
Complete guide for configuring the OpenSearch operator using environment variables.

**Contents:**
- Environment variable reference
- Configuration examples for different environments
- Security best practices
- Troubleshooting guide
- Multiple environment setup

### [OPENSEARCH_QUICKSTART.md](OPENSEARCH_QUICKSTART.md)
Quick start guide to get up and running with the OpenSearch operator.

**Contents:**
- Installation instructions
- Basic configuration
- Simple usage examples
- Common patterns
- Next steps

### [Operator Reference](../operators/opensearch.md)
Complete API documentation and technical reference.

**Contents:**
- Operator configuration parameters
- Engine and algorithm options
- Distance metrics
- API methods
- Advanced features
- Performance tuning

## Quick Links

- **Example Code:** [opensearch_integration_example.py](../../examples/opensearch_integration_example.py)
- **Example README:** [opensearch_example_README.md](../../examples/opensearch_example_README.md)
- **Unit Tests:** [tests/unit/operators/vectordb/](../../tests/unit/operators/vectordb/)

## Getting Started

### Option 1: Local Docker Setup (Recommended for Development)

1. **Start OpenSearch with Docker**
   ```bash
   docker-compose -f docker-compose.opensearch.yml up -d
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Default settings work with local Docker setup
   ```

3. **Install Dependencies**
   ```bash
   cd src/datasift_opensource/backend
   uv sync --extra dev
   ```

4. **Run Example**
   ```bash
   python examples/opensearch_integration_example.py
   ```

5. **Access OpenSearch Dashboards**
   - URL: http://localhost:5601
   - Username: `admin`
   - Password: `MyStrongPass123!`

See [DOCKER_SETUP.md](DOCKER_SETUP.md) for detailed Docker instructions.

### Option 2: Remote OpenSearch Instance

1. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your remote OpenSearch connection details
   ```

2. **Install Dependencies**
   ```bash
   cd src/datasift_opensource/backend
   uv sync --extra dev
   ```

3. **Run Example**
   ```bash
   python examples/opensearch_integration_example.py
   ```

### Documentation Reading Order

1. Start with [DOCKER_SETUP.md](DOCKER_SETUP.md) for local development
2. Or [OPENSEARCH_QUICKSTART.md](OPENSEARCH_QUICKSTART.md) for remote setup
3. Configure using [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md)
4. Reference [Operator Documentation](../operators/opensearch.md) for API details

## Support

For issues or questions:
- Check the [Troubleshooting Guide](ENVIRONMENT_SETUP.md#troubleshooting)
- Review [Example Code](../../examples/opensearch_integration_example.py)
- See [OpenSearch Documentation](https://opensearch.org/docs/latest/)