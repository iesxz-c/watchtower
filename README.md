# WatchTower

WatchTower is a hybrid monitoring and alerting platform. It provides endpoint monitoring, backend log parsing, and frontend error tracking all in one unified, self-hosted system.

## Architecture

```text
[ Frontend JS SDK ] ----> |
                          |----> [ WatchTower Ingest API ] ---> |
[ Backend Log File ] ---> |----> [ Log Parser Worker ] -------> | ---> [ Incident Engine ] ---> [ Alerter ]
                          |                                     |
[ External APIs ] <-----> |----> [ Endpoint Checker ] --------> |
```

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Configure Environment variables**:
   Copy `.env.example` to `.env` and fill in your details (like SMTP config).
   ```bash
   cp .env.example .env
   ```
3. **Configure Targets and Log Paths**:
   Edit `config.yaml` to specify the APIs you want to check and logs you want to parse.

4. **Initialize Database** (Optional if using alembic, but FastAPI will auto-create sqlite tables here):
   ```bash
   alembic upgrade head
   ```
   *(Note: For production, you should set up alembic migrations. The tables are auto-created on start if they don't exist)*

5. **Run the Application**:
   ```bash
   uvicorn watchtower.api.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Adding Monitor Targets
Modify the `monitoring.targets` section in `config.yaml`:
```yaml
monitoring:
  targets:
    - name: "My API"
      url: "https://api.myapp.com/health"
      method: GET
      expected_status: 200
```

## Integrating JS SDK

Include this in your frontend HTML:

```html
<script src="https://your-watchtower-domain.com/sdk/watchtower.js"></script>
<script>
  WatchTower.init({
    endpoint: 'https://your-watchtower-domain.com/ingest/frontend',
    apiKey: 'wt_changeme_secret_key',
    appId: 'my-frontend-app',
    environment: 'production',
    release: '1.0.0',
    sampleRate: 1.0, 
  });
</script>
```

## Pointing Log Parser
Edit `config.yaml`:
```yaml
log_sources:
  - path: "/path/to/your/app.log"
    service_name: "backend-service"
```

## Environment Variables
- `DATABASE_URL`: SQLAlchemy connection string
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`: For email alerts
- `ALERT_EMAIL`: Destination email for alerts
- `WATCHTOWER_INGEST_KEY`: Secret key for frontend SDK API ingestion
