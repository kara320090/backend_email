# Apt Alert | 이메일 알림 Backend

사용자의 지역·할인율 구독 조건을 저장하고, 조건에 맞는 새 매물을 이메일로 안내하는 FastAPI 서비스입니다.

**Python · FastAPI · Supabase · Resend · HTTPX · GitHub Actions**

## 담당 기능

| 기능 | 구현 내용 |
|---|---|
| 구독 | 이메일·지역·최소 할인율 저장, 기존 구독 재활성화 |
| 알림 | 외부 매물 API 조회 후 조건에 맞는 매물 안내 |
| 중복 확인 | `alert_logs`의 발송 이력과 매물 키 비교 |
| 구독 해제 | API 요청 또는 서명된 구독 해제 링크 처리 |
| 정기 실행 | GitHub Actions에서 보호된 `/send-alerts` 호출 |

이 저장소는 [Apt Alert Frontend](https://github.com/kara320090/apt-alert-frontend)와 연결되는 이메일 서비스입니다. 매물 데이터 수집·조회 서버는 별도로 필요합니다.

## 흐름

```text
Frontend → 구독 API → Supabase subscribers
GitHub Actions → 알림 API → 외부 매물 API → 기존 발송 이력 확인
                                            ↓
                                      Resend 메일 전송
                                            ↓
                                      alert_logs 기록
```

## 실행 준비

1. Supabase 프로젝트와 `subscribers`, `alert_logs` 테이블을 준비합니다.
2. 매물 조회 Backend, Resend 발신 설정과 테스트 수신자를 준비합니다.
3. `.env.example`을 `.env`로 복사하고 아래 환경변수를 설정합니다.

테이블 사용 필드는 [`app/main.py`](app/main.py)를 기준으로 확인합니다. `subscribers`는 `id`, `email`, `region`, `min_discount`, `is_active`, `alert_logs`는 `subscriber_id`, `listing_key`를 사용합니다. DB 스키마를 자동 생성하는 마이그레이션은 현재 저장소에 없습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# .env에 실제 실행 환경의 값을 입력한 뒤 시작합니다.
python -m uvicorn app.main:app --env-file .env --reload --port 8001
```

상태 확인은 `http://localhost:8001/health`, API 문서는 `/docs`입니다. 앱 시작 시 필수 설정과 Supabase 연결을 확인합니다.

## 필수 환경변수

| 이름 | 용도 |
|---|---|
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | 구독·발송 이력 저장 |
| `FRIEND_API_BASE_URL` | 매물 조회 서버 |
| `RESEND_API_KEY`, `MAIL_FROM` | 메일 API와 발신 주소 |
| `RESEND_TEST_RECIPIENT` | 현재 설정에서 요구하는 테스트 수신자 |
| `BACKEND_PUBLIC_BASE_URL` | 구독 해제 링크를 만들 공개 Backend 주소 |
| `CRON_SECRET` | 정기 알림 API 호출 인증 |
| `UNSUBSCRIBE_SECRET` | 구독 해제 토큰 서명 |

선택 설정은 `APP_NAME`, `APP_BASE_URL`입니다. 필수 항목의 최종 기준은 [`Settings.validate`](app/config.py)입니다.

## API

| 메서드 | 경로 | 내용 |
|---|---|---|
| GET | `/health` | 상태 확인 |
| POST | `/subscribe` | 구독 등록·재활성화; 확인 메일과 즉시 알림이 전송될 수 있음 |
| POST | `/unsubscribe` | 조건에 맞는 구독 비활성화 |
| GET | `/unsubscribe?token=...` | 서명 토큰 기반 구독 해제 |
| POST | `/send-alerts` | 활성 구독자 대상 알림; `x-cron-secret` 헤더 필요 |

## 정기 실행과 코드

[daily-send-alerts.yml](.github/workflows/daily-send-alerts.yml)은 매일 09:00 KST에 호출하도록 구성되어 있습니다. Repository Secrets의 `EMAIL_BACKEND_URL`, `CRON_SECRET`을 사용합니다. 실제 메일 전송은 배포와 외부 서비스 설정이 완료된 환경에서 발생합니다.

- [main.py](app/main.py): 구독, 매물 필터, 중복 확인과 발송 흐름
- [mailer.py](app/mailer.py): 메일 HTML과 Resend 연동
- [security.py](app/security.py): 구독 해제 토큰 생성·검증
- [schemas.py](app/schemas.py): 요청·응답 모델

