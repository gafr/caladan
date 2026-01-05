# <img src="static/logo.svg" height="50" align="center"> Caladan CalDAV Server

**Caladan** is a lightweight, Python-based CalDAV server designed for simplicity and ease of use. It provides a robust backend for calendar synchronization and a modern, user-friendly web dashboard for managing your calendars.

## Features

-   **CalDAV Support**: Full support for the CalDAV protocol, compatible with clients like Thunderbird, Apple Calendar, iOS, and Android (via DAVx5).
-   **Web Dashboard**: A beautiful web interface to view your calendars, manage shared access, and create new calendars.
-   **Calendar View**: Integrated FullCalendar view to browse your events directly in the browser.
-   **Sharing**: Easy sharing of calendars between users.
-   **Authentication**: Supports both a built-in default user (configurable) and **LDAP/Active Directory** (via Authentik, etc.).
-   **Docker Ready**: Comes with a `Dockerfile` and `docker-compose.yml` for instant deployment.

## Quick Start (Docker)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/caladan.git
    cd caladan
    ```

2.  **Configure Environment:**
    Copy the sample `.env` file (or create one) and adjust the settings.
    ```bash
    cp .env.example .env  # If provided, otherwise edit .env directly
    ```

3.  **Run with Docker Compose:**
    ```bash
    docker-compose up -d --build
    ```

4.  **Access:**
    -   **Dashboard:** Open `http://localhost:5001` (or `https` if configured).
    -   **CalDAV URL:** `http://localhost:5001/<username>/`

## Manual Installation

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Set Environment Variables (Optional):**
    ```bash
    export ENABLE_DEFAULT_USER=true
    export DEFAULT_USER=admin
    export DEFAULT_PASSWORD=secret
    ```

3.  **Run:**
    ```bash
    python3 app.py
    ```

## Configuration

Configuration is handled via environment variables, which can be set in the `.env` file.

### Default User
Used for simple setups or fallback access.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ENABLE_DEFAULT_USER` | `true` | Set to `false` to disable the built-in user. |
| `DEFAULT_USER` | `user` | Username for the built-in account. |
| `DEFAULT_PASSWORD` | `password` | Password for the built-in account. |

### LDAP Authentication (Authentik)
Integrate with an external identity provider.

| Variable | Example | Description |
| :--- | :--- | :--- |
| `LDAP_SERVER` | `ldap://10.0.0.5:3389` | Address of your LDAP server/outpost. |
| `LDAP_BASE_DN` | `dc=ldap,dc=goauthentik,dc=io` | Base DN for user search. |
| `LDAP_BIND_DN` | `cn=service_account,...` | DN of the user used to search the directory. |
| `LDAP_BIND_PASSWORD` | `secret` | Password for the bind user. |
| `LDAP_USER_FILTER` | `(uid={0})` | Filter to find users. `{0}` is replaced by the username. |

## Project Structure

-   `app.py`: Main Flask application entry point.
-   `auth.py`: Authentication logic (Local + LDAP).
-   `caldav_handler.py`: Core CalDAV protocol implementation.
-   `storage.py`: Filesystem-based storage backend.
-   `templates/`: HTML templates for the dashboard.
-   `static/`: Static assets (CSS, JS, Images).
-   `data/`: Directory where calendars and events are stored.

## License

[MIT License](LICENSE)