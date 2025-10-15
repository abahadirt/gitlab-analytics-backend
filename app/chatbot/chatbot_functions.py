
import httpx
from app.chatbot.chatbot_functions_helpers import *  # create_success_response, auth_token_missing_error, graphql_api_error, resource_not_found_error


# ---------------------
# SABITLER:
GITLAB_GRAPHQL_URL = "https://gitlab.com/api/graphql"
DEFAULT_TIMEOUT = 30
DEFAULT_PAGE_SIZE = 100  # Her bir API isteğinde çekilecek öğe sayısı
MAX_CURSOR_STEPS = 1 # Maksimum kaç sayfa (adım) çekileceği (ilk sayfa dahil)
# ---------------------



#  TEST IS NOT COMPLETE!!!
async def fetch_issues(
        gitlab_token,
        full_path: str,
        state: str = None,  # 'opened', 'closed'
        author_username: str = None,
        assignee_username: str = None,
        # milestone_title: str = None,
        search: str = None,

):
    # GraphQL sorgusu issue'lar için güncellendi
    query = """
    query($fullPath: ID!, $state: IssuableState,
          $authorUsername: String, $assigneeUsername: String,
          $search: String, $sort: IssueSort,
          $first: Int, $after: String) {
      project(fullPath: $fullPath) {
        issues(state: $state,
               authorUsername: $authorUsername, assigneeUsername: $assigneeUsername,
               search: $search, sort: $sort,
               first: $first, after: $after) {
          nodes {
            iid
            title
            state
            description # Issue'lar için açıklama alanı
            createdAt
            updatedAt
            closedAt    # Issue'lar için kapanma tarihi
            webUrl
            labels { nodes { title color } }
            author { username name avatarUrl }
            assignees { nodes { username name avatarUrl } }
            milestone { title }
            upvotes
            downvotes
            confidential
            # İhtiyaç duyabileceğiniz diğer issue alanları eklenebilir
          }
          pageInfo {
            hasNextPage
            endCursor
          }
        }
      }
    }
    """

    headers = {"Content-Type": "application/json"}
    effective_token = gitlab_token
    if not effective_token:
        return auth_token_missing_error()
    headers["Authorization"] = f"Bearer {effective_token}"

    all_issues = []
    current_after_cursor = None
    has_next_page = True
    steps_taken = 0

    # Sabit sıralama kriteri (Issue'lar için de genellikle CREATED_DESC veya UPDATED_DESC kullanılır)
    fixed_sort_order = "CREATED_DESC"  # Veya "UPDATED_DESC", "PRIORITY_DESC" vb. IssueSort enum değerleri

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        while has_next_page and steps_taken < MAX_CURSOR_STEPS:
            variables = {
                "fullPath": full_path,
                "sort": fixed_sort_order,
                "first": DEFAULT_PAGE_SIZE,
                "after": current_after_cursor
            }
            # Opsiyonel filtreleri ekle
            if state: variables["state"] = state  # GitLab GraphQL genellikle enum değerlerini büyük harf bekler
            if author_username: variables["authorUsername"] = author_username
            if assignee_username: variables["assigneeUsername"] = assignee_username
            # if milestone_title: variables["milestoneTitle"] = milestone_title
            if search: variables["search"] = search

            try:
                response = await client.post(
                    GITLAB_GRAPHQL_URL,
                    json={"query": query, "variables": variables},
                    headers=headers
                )

                if response.status_code == 200:
                    api_response_data = response.json()
                    if api_response_data.get("errors"):
                        # print(api_response_data.get("errors"))
                        error_message_prefix = f"Issue'lar çekilirken {steps_taken + 1}. sayfada" if steps_taken > 0 else "Issue'lar çekilirken"
                        return graphql_api_error(
                            custom_message=f"{error_message_prefix} GraphQL hatası oluştu.",
                            gql_errors=api_response_data["errors"]
                        )

                    project_data = api_response_data.get("data", {}).get("project")

                    if not project_data:
                        if steps_taken == 0:
                            return resource_not_found_error("proje veya issue'lar", full_path)
                        else:  # Sonraki sayfalarda proje bulunamazsa, muhtemelen bir sorun var, döngüyü kır.
                            break

                    issues_container = project_data.get("issues")
                    if issues_container and issues_container.get("nodes") is not None:
                        all_issues.extend(issues_container["nodes"])
                        page_info = issues_container.get("pageInfo", {})
                        has_next_page = page_info.get("hasNextPage", False)
                        current_after_cursor = page_info.get("endCursor")
                    else:
                        has_next_page = False  # Veri yoksa veya nodes yoksa sonraki sayfa da yoktur.

                    # İlk istekte hiç issue yoksa (ama proje varsa) boş liste döndür
                    if issues_container is None and steps_taken == 0:
                        return create_success_response({"nodes": []})


                else:  # HTTP status kodu 200 değilse
                    detail_text = ""
                    try:
                        json_body = response.json()
                        detail_text = json_body.get("message") or json_body.get("error_description") or json_body.get(
                            "error") or response.text
                    except Exception:
                        detail_text = response.text

                    error_message_prefix = f"Issue'lar çekilirken {steps_taken + 1}. sayfada" if steps_taken > 0 else "GitLab API'den issue'lar çekilirken ilk istekte"
                    return graphql_api_error(
                        status_code=response.status_code,
                        custom_message=f"{error_message_prefix} GitLab API hatası oluştu. Detay: {detail_text[:200]}"
                    )

                steps_taken += 1
                if not has_next_page:
                    break

            except httpx.TimeoutException:
                error_message_prefix = f"GitLab API isteği {steps_taken + 1}. sayfada" if steps_taken > 0 else f"GitLab API isteği ({full_path} için issue'lar) ilk istekte"
                additional_info = f" O ana kadar {len(all_issues)} issue çekildi." if steps_taken > 0 else ""
                return graphql_api_error(
                    custom_message=f"{error_message_prefix} zaman aşımına uğradı.{additional_info}")
            except httpx.RequestError as e:
                return graphql_api_error(
                    custom_message=f"GitLab API'ye ({full_path} için issue'lar) bağlanırken ağ hatası oluştu: {str(e)}")
            except Exception as e:  # Genel bir exception yakalama
                # Loglama yapmak iyi bir pratik olabilir burada
                # import logging
                # logging.exception("Unexpected error during issue fetching")
                return graphql_api_error(
                    custom_message=f"Issue'lar çekilirken sunucu tarafında beklenmedik bir hata oluştu: {str(e)}")

    return create_success_response({"nodes": all_issues})

# DUZENELEME full_path sessionStorage ile bağlanıcak, parametre olarak alınmayacak. BÜTÜN FONKSIYONLARDA
async def fetch_issues_by_author(gitlab_token,full_path: str, author_username):
    # GraphQL sorgusu güncellendi: first, after değişkenleri ve pageInfo eklendi
    query = """
    query($fullPath: ID!, $authorUsername: String!, $first: Int, $after: String) {
      project(fullPath: $fullPath) {
        issues(first: $first, after: $after, authorUsername: $authorUsername, sort: CREATED_DESC) {
          nodes {
            iid
            title
            createdAt
            webUrl
          }
          pageInfo {
            hasNextPage
            endCursor
          }
        }
      }
    }
    """

    headers = {"Content-Type": "application/json"}
    effective_token = gitlab_token
    if not effective_token:
        return auth_token_missing_error()
    headers["Authorization"] = f"Bearer {effective_token}"

    all_issues = []
    current_after_cursor = None
    has_next_page = True  # İlk isteği yapmak için true başlıyoruz
    steps_taken = 0

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        while has_next_page and steps_taken < MAX_CURSOR_STEPS:
            variables = {
                "fullPath": full_path,
                "authorUsername": author_username,
                "first": DEFAULT_PAGE_SIZE,
                "after": current_after_cursor
            }
            try:
                response = await client.post(
                    GITLAB_GRAPHQL_URL,
                    json={"query": query, "variables": variables},
                    headers=headers
                )

                if response.status_code == 200:
                    api_response_data = response.json()
                    if api_response_data.get("errors"):
                        # Eğer ilk istekte hata alınırsa veya proje bulunamazsa, doğrudan hata dön
                        if steps_taken == 0:
                            # Proje bulunamadı hatası spesifik olarak GraphQL errors içinde olabilir
                            for error in api_response_data["errors"]:
                                if error.get("message", "").startswith(
                                        "The resource that you are attempting to access does not exist or you don't have permission to perform this action"):
                                    return resource_not_found_error("proje", full_path)
                            return graphql_api_error(gql_errors=api_response_data["errors"])
                        else:  # Sonraki sayfalarda GraphQL hatası alınırsa, o ana kadar toplananlarla devam etmeyi kes.
                            # Alternatif olarak, toplananları döndürüp bir uyarı eklenebilir. Şimdilik hata ile kesiyoruz.
                            # Veya o ana kadar toplananları döndür
                            # return create_success_response({"nodes": all_issues, "pageInfo": {"warning": "Sonraki sayfalar çekilirken hata oluştu."}})
                            return graphql_api_error(
                                custom_message=f"Issue'lar çekilirken {steps_taken + 1}. sayfada GraphQL hatası oluştu.",
                                gql_errors=api_response_data["errors"]
                            )

                    project_data = api_response_data.get("data", {}).get("project")

                    if not project_data:
                        if steps_taken == 0:  # Sadece ilk adımda proje yoksa hata ver
                            return resource_not_found_error("proje", full_path)
                        else:  # Sonraki adımlarda proje null gelirse bu beklenmedik bir durumdur.
                            break  # Döngüyü sonlandır ve o ana kadar toplananları döndür.

                    issues_container = project_data.get("issues")
                    if issues_container and issues_container.get("nodes") is not None:
                        all_issues.extend(issues_container["nodes"])
                        page_info = issues_container.get("pageInfo", {})
                        has_next_page = page_info.get("hasNextPage", False)
                        current_after_cursor = page_info.get("endCursor")
                    else:
                        # "issues" alanı null veya "nodes" null ise daha fazla issue yok demektir.
                        has_next_page = False  # Döngüyü sonlandır.

                    # `issues` null ise ve ilk adımdaysak (hiç issue bulunamadı)
                    if issues_container is None and steps_taken == 0:
                        return create_success_response({"nodes": []})  # Başarılı, boş liste

                else:  # HTTP status kodu 200 değilse
                    detail_text = ""
                    try:
                        json_body = response.json()
                        detail_text = json_body.get("message") or json_body.get("error_description") or json_body.get(
                            "error") or response.text
                    except Exception:
                        detail_text = response.text

                    # Eğer ilk istekte hata alınırsa, doğrudan hata dön
                    if steps_taken == 0:
                        return graphql_api_error(
                            status_code=response.status_code,
                            custom_message=f"GitLab API'den '{author_username}' kullanıcısına ait issue'lar çekilirken ilk istekte hata oluştu. Detay: {detail_text[:200]}"
                        )
                    else:  # Sonraki sayfalarda HTTP hatası alınırsa, o ana kadar toplananları döndür ve bir uyarı ekle ya da hata ile kes.
                        # Şimdilik hata ile kesiyoruz.
                        return graphql_api_error(
                            status_code=response.status_code,
                            custom_message=f"Issue'lar çekilirken {steps_taken + 1}. sayfada GitLab API hatası oluştu. Detay: {detail_text[:200]}"
                        )

                steps_taken += 1
                if not has_next_page:  # Eğer GitLab daha fazla sayfa olmadığını belirtirse döngüyü kır
                    break

            except httpx.TimeoutException:
                if steps_taken == 0:
                    return graphql_api_error(
                        custom_message=f"GitLab API isteği ({full_path} için issue'lar) ilk istekte zaman aşımına uğradı.")
                else:
                    return graphql_api_error(
                        custom_message=f"GitLab API isteği {steps_taken + 1}. sayfada zaman aşımına uğradı. O ana kadar {len(all_issues)} issue çekildi.")
            except httpx.RequestError as e:
                return graphql_api_error(
                    custom_message=f"GitLab API'ye bağlanırken ağ hatası oluştu: {str(e)}")
            except Exception as e:  # Genel beklenmedik hata
                # print(f"Beklenmedik hata fetch_issues_by_author: {e}") # loglama için
                return graphql_api_error(
                    custom_message="Issue'lar çekilirken sunucu tarafında beklenmedik bir hata oluştu.")


    return create_success_response({"nodes": all_issues})


async def fetch_issue_details(gitlab_token,full_path: str, issue_iid):
    issue_iid = str(issue_iid)
    # Bu fonksiyon değişmedi, sayfalama ile ilgisi yok.
    url = "https://gitlab.com/api/graphql"
    query = """
    query($fullPath: ID!, $issueIid: String!) {
      project(fullPath: $fullPath) {
        issue(iid: $issueIid) {
          id
          iid
          title
          description
          state
          createdAt
          updatedAt
          closedAt
          webUrl
          author {
            username
            name
          }
          assignees {
            nodes {
              username
              name
            }
          }
          labels {
            nodes {
              title
              color
            }
          }
        }
      }
    }
    """

    variables = {
        "fullPath": full_path,
        "issueIid": issue_iid
    }

    headers = {"Content-Type": "application/json"}
    effective_token = gitlab_token
    if not effective_token:
        return auth_token_missing_error()

    headers["Authorization"] = f"Bearer {effective_token}"

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        try:
            response = await client.post(
                url,
                json={"query": query, "variables": variables},
                headers=headers
            )
            if response.status_code == 200:
                api_response_data = response.json()
                if api_response_data.get("errors"):
                    return graphql_api_error(gql_errors=api_response_data["errors"])

                project_data = api_response_data.get("data", {}).get("project")
                if not project_data:
                    return resource_not_found_error("proje", full_path)

                issue_data = project_data.get("issue")
                if issue_data:
                    return create_success_response(issue_data)
                else:
                    return resource_not_found_error("issue", f"'{full_path}' projesindeki #{issue_iid} IID'li")
            else:
                detail_text = ""
                try:
                    json_body = response.json()
                    detail_text = json_body.get("message") or json_body.get("error_description") or json_body.get(
                        "error") or response.text
                except Exception:
                    detail_text = response.text
                return graphql_api_error(
                    status_code=response.status_code,
                    custom_message=f"GitLab API'den issue #{issue_iid} detayları çekilirken hata oluştu. Detay: {detail_text[:200]}"
                )
        except httpx.TimeoutException:
            return graphql_api_error(
                custom_message=f"GitLab API isteği (issue #{issue_iid} detayları için {full_path}) zaman aşımına uğradı.")
        except httpx.RequestError as e:
            return graphql_api_error(
                custom_message=f"GitLab API'ye (issue #{issue_iid} detayları için {full_path}) bağlanırken bir ağ hatası oluştu: {str(e)}")
        except Exception as e:
            return graphql_api_error(
                custom_message="Issue detayları çekilirken sunucu tarafında beklenmedik bir hata oluştu.")


async def fetch_merge_requests(
        gitlab_token,
        full_path: str,
        state: str = None, # 'opened', 'closed', 'locked', 'merged'
        author_username: str = None,
        assignee_username: str = None,
        reviewer_username: str = None,
        search: str = None,
):
    # GraphQL sorgusu güncellendi: first, after değişkenleri ve pageInfo eklendi
    query = """
    query($fullPath: ID!, $state: MergeRequestState,
          $authorUsername: String, $assigneeUsername: String,
          $reviewerUsername: String, $search: String, $sort: MergeRequestSort,
          $first: Int, $after: String) {
      project(fullPath: $fullPath) {
        mergeRequests(state: $state,
                      authorUsername: $authorUsername, assigneeUsername: $assigneeUsername,
                      reviewerUsername: $reviewerUsername, search: $search, sort: $sort,
                      first: $first, after: $after) {
          nodes {
            iid
            title
            state
            sourceBranch
            targetBranch
            createdAt
            updatedAt
            webUrl
            labels { nodes { title } }
            author { username name }
            assignees { nodes { username name } }
          }
          pageInfo {
            hasNextPage
            endCursor
          }
        }
      }
    }
    """

    headers = {"Content-Type": "application/json"}
    effective_token = gitlab_token
    if not effective_token:
        return auth_token_missing_error()
    headers["Authorization"] = f"Bearer {effective_token}"

    all_mrs = []
    current_after_cursor = None
    has_next_page = True  # İlk isteği yapmak için true başlıyoruz
    steps_taken = 0

    # Sabit sıralama kriteri
    fixed_sort_order = "CREATED_DESC"

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        while has_next_page and steps_taken < MAX_CURSOR_STEPS:
            variables = {
                "fullPath": full_path,
                "sort": fixed_sort_order,
                "first": DEFAULT_PAGE_SIZE,
                "after": current_after_cursor
            }
            # Opsiyonel filtreleri ekle
            if state: variables["state"] = state
            if author_username: variables["authorUsername"] = author_username
            if assignee_username: variables["assigneeUsername"] = assignee_username
            if reviewer_username: variables["reviewerUsername"] = reviewer_username
            if search: variables["search"] = search

            try:
                response = await client.post(
                    GITLAB_GRAPHQL_URL,
                    json={"query": query, "variables": variables},
                    headers=headers
                )

                if response.status_code == 200:
                    api_response_data = response.json()
                    if api_response_data.get("errors"):
                        if steps_taken == 0:
                            return graphql_api_error(gql_errors=api_response_data["errors"])
                        else:
                            return graphql_api_error(
                                custom_message=f"Merge Requests çekilirken {steps_taken + 1}. sayfada GraphQL hatası oluştu.",
                                gql_errors=api_response_data["errors"]
                            )

                    project_data = api_response_data.get("data", {}).get("project")

                    if not project_data:
                        if steps_taken == 0:
                            return resource_not_found_error("proje veya birleştirme istekleri", full_path)
                        else:
                            break

                    mrs_container = project_data.get("mergeRequests")
                    if mrs_container and mrs_container.get("nodes") is not None:
                        all_mrs.extend(mrs_container["nodes"])
                        page_info = mrs_container.get("pageInfo", {})
                        has_next_page = page_info.get("hasNextPage", False)
                        current_after_cursor = page_info.get("endCursor")
                    else:
                        has_next_page = False

                    if mrs_container is None and steps_taken == 0:
                        return create_success_response({"nodes": []})


                else:  # HTTP status kodu 200 değilse
                    detail_text = ""
                    try:
                        json_body = response.json()
                        detail_text = json_body.get("message") or json_body.get("error_description") or json_body.get(
                            "error") or response.text
                    except Exception:
                        detail_text = response.text

                    if steps_taken == 0:
                        return graphql_api_error(
                            status_code=response.status_code,
                            custom_message=f"GitLab API'den birleştirme istekleri çekilirken ilk istekte hata oluştu. Detay: {detail_text[:200]}"
                        )
                    else:
                        return graphql_api_error(
                            status_code=response.status_code,
                            custom_message=f"Birleştirme istekleri çekilirken {steps_taken + 1}. sayfada GitLab API hatası oluştu. Detay: {detail_text[:200]}"
                        )

                steps_taken += 1
                if not has_next_page:
                    break

            except httpx.TimeoutException:
                if steps_taken == 0:
                    return graphql_api_error(
                        custom_message=f"GitLab API isteği ({full_path} için MR'lar) istekte zaman aşımına uğradı.")
                else:
                    return graphql_api_error(
                        custom_message=f"GitLab API isteği {steps_taken + 1}. sayfada zaman aşımına uğradı. O ana kadar {len(all_mrs)} MR çekildi.")
            except httpx.RequestError as e:
                    return graphql_api_error(
                        custom_message=f"GitLab API'ye ({full_path} için MR'lar) bağlanırken ağ hatası oluştu: {str(e)}")
            except Exception as e:
                return graphql_api_error(
                    custom_message="Birleştirme istekleri çekilirken sunucu tarafında beklenmedik bir hata oluştu.")


    return create_success_response({"nodes": all_mrs})


async def fetch_merge_request_details(gitlab_token,full_path: str, mr_iid):
    mr_iid = str(mr_iid)
    url = "https://gitlab.com/api/graphql"
    query = """
    query($fullPath: ID!, $mrIid: String!) {
      project(fullPath: $fullPath) {
        mergeRequest(iid: $mrIid) {
          id
          iid
          title
          description
          state 
          createdAt
          updatedAt
          mergedAt
          sourceBranch
          targetBranch
          webUrl
          headPipeline { id status detailedStatus { text label } }
          conflicts
          draft
          mergeable
          author { username name }
          assignees { nodes { username name } }
          reviewers { nodes { username name } }
          labels { nodes { title description } }
          milestone { title dueDate }
        }
      }
    }
    """
    variables = {
        "fullPath": full_path,
        "mrIid": mr_iid
    }
    headers = {"Content-Type": "application/json"}

    effective_token = gitlab_token
    if not effective_token:
        return auth_token_missing_error()
    headers["Authorization"] = f"Bearer {effective_token}"

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        try:
            response = await client.post(url, json={"query": query, "variables": variables}, headers=headers)
            if response.status_code == 200:
                api_response_data = response.json()
                if api_response_data.get("errors"):
                    return graphql_api_error(gql_errors=api_response_data["errors"])
                project_data = api_response_data.get("data", {}).get("project")
                if project_data and project_data.get("mergeRequest"):
                    return create_success_response(project_data["mergeRequest"])
                else:
                    # Daha spesifik hata mesajı
                    not_found_message = f"'{full_path}' projesinde '{mr_iid}' IID'li birleştirme isteği bulunamadı."
                    if not project_data:  # Projenin kendisi bulunamadıysa
                        not_found_message = f"'{full_path}' projesi bulunamadı veya bu projeye erişim yetkiniz yok."
                    # resource_not_found_error helper'ını kullanalım
                    return resource_not_found_error("birleştirme isteği", f"'{full_path}' projesindeki MR#{mr_iid}")
            else:
                detail_text = ""
                try:
                    json_body = response.json()  # JSON parse etmeyi dene
                    detail_text = json_body.get("message") or json_body.get("error_description") or json_body.get(
                        "error") or response.text
                except Exception:  # JSON parse edilemezse veya beklenen anahtarlar yoksa
                    detail_text = response.text
                return graphql_api_error(status_code=response.status_code,
                                         custom_message=f"GitLab API'den MR #{mr_iid} detayları çekilirken hata oluştu. Detay: {detail_text[:200]}")
        except httpx.TimeoutException:
            return graphql_api_error(
                custom_message=f"GitLab API isteği (MR #{mr_iid} detayları için {full_path}) zaman aşımına uğradı.")
        except httpx.RequestError as e:
            return graphql_api_error(
                custom_message=f"GitLab API'ye (MR #{mr_iid} detayları için {full_path}) bağlanırken bir ağ hatası oluştu: {str(e)}")
        except Exception as e:
            # print(f"Beklenmedik bir hata oluştu: fetch_merge_request_details - {str(e)}") # Geliştirme sırasında loglama için
            return graphql_api_error(
                custom_message="Birleştirme isteği detayları çekilirken sunucu tarafında beklenmedik bir hata oluştu.")