from __future__ import annotations

import typing as t
import urllib.parse

import google.oauth2.service_account
import googleapiclient.discovery
import pydantic as p
from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Configuration, Container, Provider, Singleton
from livekit import api as livekit_api  # pyright: ignore [reportMissingTypeStubs]

if t.TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import SheetsResource  # pyright: ignore [reportMissingModuleSource]


class GoogleContainer(DeclarativeContainer):
    @staticmethod
    def provide_creds(
        project_id: str, private_key_id: str, private_key: p.Secret[str], client_email: p.EmailStr, client_id: str
    ) -> google.oauth2.service_account.Credentials:
        import google.oauth2.service_account  # noqa: F821

        qe = urllib.parse.quote(client_email)
        client_x509_cert_url = f"https://www.googleapis.com/robot/v1/metadata/x509/{qe}"
        info = {
            "project_id": project_id,
            "private_key_id": private_key_id,
            "private_key": private_key.get_secret_value(),
            "client_email": client_email,
            "client_id": client_id,
            "type": "service_account",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": client_x509_cert_url,
            "universe_domain": "googleapis.com",
        }
        return google.oauth2.service_account.Credentials.from_service_account_info(info)

    @t.overload
    @staticmethod
    def provide_service(
        credentials: google.oauth2.service_account.Credentials,
        service_name: t.Literal["sheets"],
        service_version: t.Literal["v4"],
    ) -> SheetsResource.SpreadsheetsResource: ...

    @t.overload
    @staticmethod
    def provide_service(
        credentials: google.oauth2.service_account.Credentials, service_name: str, service_version: t.Literal["v4"]
    ) -> googleapiclient.discovery.Resource: ...

    @staticmethod
    def provide_service(
        credentials: google.oauth2.service_account.Credentials,
        service_name: t.Literal["sheets"] | str,
        service_version: str,
    ) -> googleapiclient.discovery.Resource:
        service = googleapiclient.discovery.build(service_name, service_version, credentials=credentials)
        match service_name:
            case "sheets":
                return service.spreadsheets()  # pyright: ignore [reportAttributeAccessIssue, reportUnknownVariableType]
            case _:
                raise KeyError(service_name)

    config: Configuration = Configuration(strict=True)
    secrets: Configuration = Configuration(strict=True)

    credentials: Provider[google.oauth2.service_account.Credentials] = Singleton(
        provide_creds,
        project_id=config.service_account.project_id,
        private_key_id=config.service_account.private_key_id,
        private_key=secrets.service_account.private_key,
        client_email=config.service_account.client_email,
        client_id=config.service_account.client_id,
    )
    sheets: Provider[SheetsResource.SpreadsheetsResource] = Singleton(
        provide_service, service_name="sheets", service_version="v4", credentials=credentials
    )


class LiveKitContainer(DeclarativeContainer):
    @staticmethod
    def provide_api(url: str, api_key: p.Secret[str], api_secret: p.Secret[str]) -> livekit_api.LiveKitAPI:
        return livekit_api.LiveKitAPI(
            url=url,
            api_key=api_key.get_secret_value(),
            api_secret=api_secret.get_secret_value(),
        )

    @staticmethod
    def provide_access_token(api_key: p.Secret[str], api_secret: p.Secret[str]) -> livekit_api.AccessToken:
        return livekit_api.AccessToken(
            api_key=api_key.get_secret_value(),
            api_secret=api_secret.get_secret_value(),
        )

    config: Configuration = Configuration(strict=True)
    secrets: Configuration = Configuration(strict=True)

    api: Provider[livekit_api.LiveKitAPI] = Singleton(
        provide_api,
        url=config.url,
        api_key=secrets.api_key,
        api_secret=secrets.api_secret,
    )


class VendorContainer(DeclarativeContainer):
    config: Configuration = Configuration()
    secrets: Configuration = Configuration()

    google: Provider[GoogleContainer] = Container(GoogleContainer, config=config.google, secrets=secrets.google)
    livekit: Provider[LiveKitContainer] = Container(LiveKitContainer, config=config.livekit, secrets=secrets.livekit)
