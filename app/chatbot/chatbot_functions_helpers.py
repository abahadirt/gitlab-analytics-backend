def create_error_response(error_code: str, message: str, details=None, status_code: int = 0):
    """Genel bir hata yanıtı oluşturur."""
    response = {
        "status": "error",
        "error_code": error_code,
        "message": message,
    }
    return response

def auth_token_missing_error():
    return create_error_response(
        error_code="AUTH_TOKEN_MISSING",
        message="GitLab API ile iletişim kurmak için gerekli kimlik doğrulama bilgisi (token) bulunamadı. "
                "Bu nedenle istenen işlem gerçekleştirilemedi. Lütfen geliştirici ile iletişime geçin"
    )

def undefined_error():
    return create_error_response(
        error_code="UNDEFINED",
        message="GitLab API ile iletişim kurarken bir hata ile karşılaşıldı."
                "Bu nedenle istenen işlem gerçekleştirilemedi. Lütfen geliştirici ile iletişime geçin"
    )


def graphql_api_error(status_code=None, gql_errors=None, custom_message=None):
    if gql_errors:
        error_messages = [err.get("message", "Bilinmeyen GraphQL hatası") for err in gql_errors]
        message = custom_message or f"GitLab API'den GraphQL hatası alındı: {', '.join(error_messages)}"
        return create_error_response(
            error_code="GRAPHQL_ERROR",
            message=message,
            details=gql_errors
        )
    elif status_code:
        message = custom_message or f"GitLab API isteği başarısız oldu. Durum Kodu: {status_code}."
        return create_error_response(
            error_code=f"HTTP_ERROR_{status_code}",
            message=message
        )
    return create_error_response(
        error_code="API_REQUEST_ERROR",
        message=custom_message or "GitLab API'den veri istenirken bilinmeyen bir hata oluştu."
    )

def resource_not_found_error(resource_type: str = "Kaynak", resource_name: str = ""):
    message = f"Belirtilen {resource_type} bulunamadı."
    if resource_name:
        message = f"'{resource_name}' adlı {resource_type} bulunamadı."
    return create_error_response(
        error_code="RESOURCE_NOT_FOUND",
        message=message
    )










def create_success_response(data: any):
    return {
        "status": "success",
        "data": data
    }