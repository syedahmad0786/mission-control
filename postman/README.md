# Postman

`openapi.json` is generated from FastAPI. The collection is converted from that contract and adds only a failed-run replay, run chaining, and assertions. The environment contains no secrets.

```powershell
postman-cli collection run postman/agentops-mission-control.postman_collection.json -e postman/agentops-mission-control.postman_environment.json --bail
```
