# Notion 설정 및 운영 가이드

이 문서는 `study-manager`의 Notion 연동 구조와 운영 시 필요한 설정을 설명합니다.

---

## 1. Notion 연동 구조

`study-manager`는 Notion API를 사용하여 다음 작업을 수행합니다.

- 문제 페이지 생성
- 기존 문제 metadata 갱신
- 문제와 스터디 Relation 연결
- 스터디별 문제 개수 계산
- OJ별 View 생성 및 갱신

전체 구조는 다음과 같습니다.

```text
Discord
   ↓
study-manager
   ↓
Notion API
   ↓
스터디 DB / 각 OJ 문제 DB
```

---

## 2. 필요한 환경 변수

```env
NOTION_TOKEN=
NOTION_STUDY_DATA_SOURCE_ID=
NOTION_BOJ_DATA_SOURCE_ID=
NOTION_CODEFORCES_DATA_SOURCE_ID=
NOTION_PROGRAMMERS_DATA_SOURCE_ID=
```

### NOTION_TOKEN

Notion API 요청 인증에 사용합니다.

가장 중요한 비밀 값이며 GitHub에 커밋하면 안 됩니다.

현재 운영 환경의 Token 만료 예정일:

```text
2027-09-20
```

만료 전에 반드시 교체 또는 갱신해야 합니다.

### NOTION_STUDY_DATA_SOURCE_ID

스터디 데이터베이스의 Data Source ID입니다.

### NOTION_<OJ>_DATA_SOURCE_ID

각 Online Judge 문제 데이터베이스의 Data Source ID입니다.

예:

```text
NOTION_BOJ_DATA_SOURCE_ID
NOTION_CODEFORCES_DATA_SOURCE_ID
NOTION_PROGRAMMERS_DATA_SOURCE_ID
```

새 OJ를 추가할 경우 해당 OJ의 Data Source ID 환경 변수도 추가합니다.

---

## 3. Notion Integration 권한

새로운 문제 DB를 만들거나 DB 구조를 변경하는 경우 해당 Database가 `SOLUTIO Study Manager` Integration에서 접근 가능하도록 연결되어 있어야 합니다.

DB를 만들고 Data Source ID만 등록했다고 해서 자동으로 API에서 접근 가능한 것은 아닙니다.

새 OJ 추가 시 반드시 다음을 확인합니다.

```text
[ ] OJ 문제 Database 생성
[ ] 📚 스터디 데이터베이스 Relation 생성
[ ] SOLUTIO Study Manager Integration 연결
[ ] Data Source ID 확인
[ ] 배포 환경 변수 추가
```

---

## 4. NOTION_TOKEN 만료 시 증상

Token이 만료되거나 잘못된 값으로 설정되면 Discord Bot 프로세스 자체는 정상적으로 실행될 수 있습니다.

그러나 `/문제등록` 실행 과정에서 Notion API 요청이 실패합니다.

따라서 다음과 같은 상황이라면 Token을 우선 확인합니다.

```text
Discord Bot은 온라인 상태임
OJ 문제 정보도 정상적으로 가져옴
하지만 Notion 문제 생성/갱신에서 인증 오류 발생
```

---

## 5. NOTION_TOKEN 갱신 절차

현재 Token이 만료되기 전에 새로운 Token을 발급합니다.

새 Token을 발급한 뒤 실제 Token 값은 GitHub 코드나 문서에 작성하지 않습니다.

배포 환경에서:

```text
NOTION_TOKEN
```

값을 새로운 Token으로 교체합니다.

그 다음 Bot을 재배포 또는 재시작합니다.

배포 방식이 변경되었을 수 있으므로 현재 GitHub Actions / Docker 설정을 확인한 뒤 적용합니다.

---

## 6. Token 갱신 후 확인

갱신 후 실제 Discord에서 테스트합니다.

```text
/문제등록
```

테스트용 문제 하나를 등록하고 다음 항목을 확인합니다.

```text
[ ] 문제 metadata 조회 성공
[ ] Notion 문제 페이지 생성 또는 갱신 성공
[ ] 스터디 Relation 연결 성공
[ ] 스터디 View 갱신 성공
[ ] Discord에서 등록 완료 메시지 출력
```

모두 정상이라면 Token 교체가 완료된 것입니다.

---

## 7. 보안 주의사항

다음 값은 GitHub에 커밋하지 않습니다.

```text
NOTION_TOKEN
DISCORD_BOT_TOKEN
```

`.env`는 Git에서 제외되어 있어야 합니다.

`.env.example`에는 변수 이름만 작성합니다.

예:

```env
NOTION_TOKEN=
DISCORD_BOT_TOKEN=
```

실제 값은 작성하지 않습니다.

Token이 외부에 노출된 경우 만료일까지 기다리지 말고 즉시 기존 Token을 폐기 또는 교체해야 합니다.

---

## 8. 운영 인수인계

현재 운영 Token은 영구적인 값이라고 가정하지 않습니다.

운영 담당자가 변경되더라도 다음 정보를 후임 개발자가 알 수 있어야 합니다.

```text
Token을 어디서 발급하는지
Token을 어디에 적용하는지
Token 만료일
배포 환경 변수를 어디서 수정하는지
Token 변경 후 서비스를 어떻게 재시작하는지
```

배포 구조가 변경될 경우 이 문서도 함께 갱신합니다.