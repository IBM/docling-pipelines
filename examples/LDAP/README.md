                        # LDAP Server Setup Guide

## Overview

This guide provides instructions for setting up a local LDAP server for docpipe authentication and OAuth2 integration. The setup uses OpenLDAP with phpLDAPAdmin for easy management through a web interface.

The LDAP server is configured with:
- Organization: ABC Inc
- Domain: abc.com
- Base DN: `dc=abc,dc=com`
- Pre-configured test users for authentication testing

## Prerequisites

- **Docker** or **Podman** installed on your system
- **docker-compose** or **podman-compose** available
- **ldap-utils** package (for command-line verification)
  - Ubuntu/Debian: `sudo apt-get install ldap-utils`
  - macOS: `brew install openldap`
  - RHEL/Fedora: `sudo dnf install openldap-clients`

## Quick Start

### 1. Configure Environment Variables

Copy the example environment file and customize if needed:

```bash
cd examples/LDAP
cp .env.example .env
```

Edit `.env` to set your passwords (recommended for production):
```bash
LDAP_ORGANIZATION=ABCInc
LDAP_DOMAIN=abc.com
LDAP_ADMIN_PASSWORD=
TEST_USER_PASSWORD=
```

**Security Note**: The `.env` file is gitignored to prevent committing sensitive credentials.

### 2. Start the LDAP Server

Navigate to the LDAP directory and start the services:

```bash
cd examples/LDAP

# Using Docker
docker-compose up -d

# Using Podman
podman-compose up -d
```

This will start two containers:
- `local-ldap`: OpenLDAP server (ports 1389, 1636)
- `local-ldap-admin`: phpLDAPAdmin web interface (port 8085)

### 3. Load User Data

After the containers are running, load the test users into LDAP:

```bash
# Load ABC Inc users (Alice Baker and Jane Smith)
ldapadd -x -H ldap://localhost:1389 -D "cn=admin,dc=abc,dc=com" -w changeme -f abc_users.ldif
```

**Note:** 
- Replace `changeme` with your `LDAP_ADMIN_PASSWORD` from `.env` if you changed it
- If you see "Already exists" errors, the users are already loaded. This is normal if you've run these commands before.

### 4. Verify Setup

Check that users are loaded correctly:

```bash
ldapsearch -x -H ldap://localhost:1389 -D "cn=admin,dc=abc,dc=com" -w changeme -b "ou=People,dc=abc,dc=com"
```

You should see entries for both `abaker` and `jsmith`.

## LDIF Files

### abc_users.ldif

Creates the organizational structure and test users:
- **Organizational Unit**: `ou=People,dc=abc,dc=com`
- **User**: Alice Baker (abaker)
  - Email: abaker@abc.com
  - Password: set via `TEST_USER_PASSWORD` in `.env`
  - UID: 1003
- **User**: Jane Smith (jsmith)
  - Email: jsmith@abc.com
  - Password: set via `TEST_USER_PASSWORD` in `.env`
  - UID: 1002

Both users have the following object classes:
- `inetOrgPerson`: Standard person entry
- `posixAccount`: UNIX account attributes
- `shadowAccount`: Password aging attributes

## Accessing phpLDAPAdmin

### Web Interface

1. Open your browser and navigate to: **http://localhost:8085**
2. Click "login" on the left sidebar
3. Enter admin credentials:
   - **Login DN**: `cn=admin,dc=abc,dc=com`
   - **Password**: `changeme` (or your custom password from `.env`)

### Browsing Users

After logging in:
1. Expand the tree: `dc=abc,dc=com`
2. Click on `ou=People`
3. You'll see entries for `abaker` and `jsmith`

### Managing Users

Through phpLDAPAdmin you can:
- View user attributes
- Modify user properties
- Add new users
- Delete users
- Change passwords

## Default Credentials

### LDAP Admin

- **DN**: `cn=admin,dc=abc,dc=com`
- **Password**: `changeme` (default, customize in `.env`)
- **Server**: `localhost:1389`
- **Base DN**: `dc=abc,dc=com`

### Test Users

#### Alice Baker
- **Username**: `abaker`
- **Password**: `changeme` (default, customize in `.env`)
- **Email**: `abaker@abc.com`
- **DN**: `cn=Alice Baker,ou=People,dc=abc,dc=com`

#### Jane Smith
- **Username**: `jsmith`
- **Password**: `changeme` (default, customize in `.env`)
- **Email**: `jsmith@abc.com`
- **DN**: `cn=Jane Smith,ou=People,dc=abc,dc=com`

## Verifying Setup

### Check Container Status

```bash
# Docker
docker ps | grep ldap

# Podman
podman ps | grep ldap
```

You should see both `local-ldap` and `local-ldap-admin` containers running.

### Test LDAP Connection

```bash
# Test admin bind
ldapwhoami -x -H ldap://localhost:1389 -D "cn=admin,dc=abc,dc=com" -w changeme

# Expected output: dn:cn=admin,dc=abc,dc=com
```

### Test User Authentication

```bash
# Test Alice Baker authentication
ldapwhoami -x -H ldap://localhost:1389 -D "cn=Alice Baker,ou=People,dc=abc,dc=com" -w changeme

# Test Jane Smith authentication
ldapwhoami -x -H ldap://localhost:1389 -D "cn=Jane Smith,ou=People,dc=abc,dc=com" -w changeme
```

### Search for All Users

```bash
ldapsearch -x -H ldap://localhost:1389 -D "cn=admin,dc=abc,dc=com" -w changeme \
  -b "ou=People,dc=abc,dc=com" "(objectClass=inetOrgPerson)" cn mail uid
```

## Troubleshooting

### Containers Won't Start

**Issue**: Port conflicts (8085, 1389, or 1636 already in use)

**Solution**: 
- Check what's using the ports: `lsof -i :8085` or `netstat -an | grep 8085`
- Stop conflicting services or modify ports in `docker-compose.yml`

### Cannot Connect to LDAP

**Issue**: Connection refused to localhost:1389

**Solution**:
1. Verify containers are running: `docker ps` or `podman ps`
2. Check container logs: `docker logs local-ldap` or `podman logs local-ldap`
3. Ensure firewall isn't blocking ports
4. Try restarting containers: `docker-compose restart` or `podman-compose restart`

### Users Not Found

**Issue**: ldapsearch returns no results

**Solution**:
1. Verify users were loaded: Check for "Already exists" or success messages when running ldapadd
2. Re-run the ldapadd commands with the LDIF files
3. Check phpLDAPAdmin to see if users exist
4. Verify Base DN is correct: `dc=abc,dc=com`

### Authentication Fails

**Issue**: User authentication returns "Invalid credentials"

**Solution**:
1. Verify password matches what's in your `.env` file (default: `changeme`)
2. Check DN format is correct: `cn=Alice Baker,ou=People,dc=abc,dc=com`
3. Use phpLDAPAdmin to verify user exists and check attributes
4. Try resetting password through phpLDAPAdmin

### phpLDAPAdmin Not Accessible

**Issue**: Cannot access http://localhost:8085

**Solution**:
1. Verify `local-ldap-admin` container is running
2. Check container logs: `docker logs local-ldap-admin`
3. Try accessing via container IP instead of localhost
4. Clear browser cache or try incognito mode

### LDIF Import Errors

**Issue**: "No such object" error when running ldapadd

**Solution**:
1. Ensure OpenLDAP container is fully started (wait 10-15 seconds after `up -d`)
2. Verify Base DN exists: `ldapsearch -x -H ldap://localhost:1389 -D "cn=admin,dc=abc,dc=com" -w changeme -b "dc=abc,dc=com"`
3. Load `abc_users.ldif` (creates `ou=People` and both users)

## Stopping the LDAP Server

To stop the LDAP services:

```bash
# Docker
docker-compose down

# Podman
podman-compose down
```

To stop and remove all data (reset to clean state):

```bash
# Docker
docker-compose down -v

# Podman
podman-compose down -v
```

## Integration with Docling Pipelines

Once LDAP is running, configure Docling Pipelines to use it for authentication:

1. Set environment variables in your `.env`:
   ```
   LDAP_SERVER=localhost
   LDAP_PORT=1389
   LDAP_BASE_DN=dc=abc,dc=com
   LDAP_USER_DN=ou=People,dc=abc,dc=com
   LDAP_BIND_DN=cn=admin,dc=abc,dc=com
   LDAP_BIND_PASSWORD=
   ```

2. Test authentication with Docling Pipelines API using test user credentials

3. For OAuth2 integration, refer to [OAuth2 Authentication Guide](../../docs/api/OAUTH2_AUTHENTICATION.md)

## Additional Resources

- [OpenLDAP Documentation](https://www.openldap.org/doc/)
- [phpLDAPAdmin Documentation](http://phpldapadmin.sourceforge.net/wiki/index.php/Main_Page)
- [LDIF Format Specification](https://tools.ietf.org/html/rfc2849)