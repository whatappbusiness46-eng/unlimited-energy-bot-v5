# Deployment checklist

1. Create a Render Web Service.
2. Add all required environment variables from `.env.example`.
3. Set `PUBLIC_BASE_URL` to the service's public HTTPS URL.
4. Confirm MongoDB Network Access allows the Render service to connect.
5. Confirm the Telegram bot token is valid.
6. Configure CPAGrip offer API/feed using the provider's documented endpoint.
7. Configure CPAGrip postback with the exact user-id/event-id/reward parameters.
8. Configure the postback secret/signature exactly as documented.
9. Test one provider conversion in a controlled/test environment.
10. Verify: provider callback -> duplicate check -> MongoDB event -> user balance -> transaction.
11. Configure ShrtFly/ShrinkMe using their current official API documentation.
12. Do not credit users merely because they clicked a shortlink or pressed Verify.
13. Test withdrawal/admin approval before public launch.
