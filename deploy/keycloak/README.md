# Local OIDC provider

This realm is a disposable local development fixture. Product roles and tenant/workspace memberships are held in the application database; Keycloak supplies identity only. The users admin, analyst, editor, viewer, and outsider have stable IDs in `render_realm.py`. The outsider belongs to the second tenant in the application bootstrap.

Supply generated `KOINON_DEMO_PASSWORD` and `KOINON_OIDC_CLIENT_SECRET` privately through the environment. Run `python deploy/keycloak/render_realm.py /private/runtime/import/koinon-realm.json`, then start Keycloak with that import directory and `--import-realm`. The renderer refuses to overwrite an existing file and writes mode 0600. Keep generated realm JSON outside the repository.

Use issuer `http://127.0.0.1:18784/realms/koinon`, browser client `koinon-browser`, API audience `koinon-api`, and exact callback `http://127.0.0.1:18781/login/oauth2/code/koinon`. Start login at `/oauth2/authorization/koinon`; browser calls use `/bff/**` and `/auth/me`, API tokens use `/api/**`. Authorization Code uses PKCE S256; password grant and self-registration are disabled. Use `/logout` POST with the matching XSRF token to end the application session.

For local Keycloak 26.8.1 with PostgreSQL, configure `KC_DB=postgres`, `KC_DB_URL=jdbc:postgresql://127.0.0.1:18783/keycloak`, `KC_DB_USERNAME`, `KC_DB_PASSWORD`, `KC_BOOTSTRAP_ADMIN_USERNAME`, `KC_BOOTSTRAP_ADMIN_PASSWORD`, `JAVA_OPTS_KC_HEAP=-Xms128m -Xmx512m` and `KC_HTTP_PORT=18784`. Run `bin/kc.sh start-dev --http-host=127.0.0.1 --hostname=http://127.0.0.1:18784 --import-realm`. Bind only the owned loopback ports. Do not reuse this local configuration in production.

Production uses HTTPS, secure cookies, a shared native session store, separately managed identity provisioning, independent credentials and explicit membership bootstrap. No production user/password is defined here. Entra and Google are supported through explicit OIDC endpoints/clients; live provider acceptance requires the operator's registered client and has not been established by the local tests.
