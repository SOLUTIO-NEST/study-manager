# solved.ac v4 API 연동 가이드

## 1. 개편 내용과 공식 자료

2026년 11월 17일 공식 API가 공개되었으며, 기존 `/api/v3/*`는 지원 종료 예정입니다.

- [공식 API 제공 공지](https://solved.ac/en/notices/261117-api)
- [2026년 11월 11일 개편 공지](https://solved.ac/en/notices/v4)
- [공식 API 문서](https://backstage.solved.ac/developer/docs)
- [공개 OpenAPI 명세](https://backstage.solved.ac/api/v4/openapi)
- [DOJ 연동 공지](https://solved.ac/en/notices/261120-doj)

이 프로젝트는 공식 명세의 다음 API를 사용합니다.

| API | 용도 |
| --- | --- |
| `GET /api/v4/judges` | 연계 OJ의 ID와 검색용 접두사 확인 |
| `GET /api/v4/problems?q=id:B1000` | 원래 OJ 문제 번호를 solved.ac 번호로 변환 |
| `GET /api/v4/problems/{problemId}?sub={subId}` | 문제 제목, 레벨, 태그 키, OJ 대응 번호 조회 |
| `GET /api/v4/tags` | 태그 키에 대응하는 한국어 이름 조회 |

`id:` 뒤에 OJ의 접두사와 원래 번호를 붙이는 검색 문법은 공식 사이트 검색창의 필터 도움말에 안내되어 있습니다. 접두사를 코드에 고정하지 않고 `/judges` 응답에서 가져옵니다. 검색 결과의 `judgeIds`도 대조합니다.

태그와 OJ 목록은 메모리에 10분간 캐시합니다.

## 2. API 앱 설정

1. [solved.ac Backstage](https://backstage.solved.ac/developer/apps)에 로그인해 앱을 생성합니다.
2. 클라이언트 ID와 시크릿을 발급받습니다.
3. 로컬 `.env`와 배포 서버 `.env`에 다음 값을 설정합니다.

```env
SOLVEDAC_CLIENT_ID=
SOLVEDAC_CLIENT_SECRET=
```

모든 v4 API 요청에 `x-client-id`와 `x-client-secret` 헤더가 필요합니다. 이 봇은 공개 문제 정보만 사용하므로 사용자 OAuth 로그인은 필요하지 않습니다.

앱 시크릿은 코드, 문서, Discord 메시지에 넣지 않습니다. 설정 후 봇을 재시작합니다.

## 3. 입력할 수 있는 URL

```text
https://solved.ac/p/1000
https://solved.ac/en/p/19917a
https://www.acmicpc.net/problem/1000
https://doj.kr/ko/problems/1050
https://jungol.co.kr/problem/3522
https://www.jungol.co.kr/bbs/board.php?bo_table=pbank&wr_id=1001
```

solved.ac URL은 해당 문제의 `problemId`와 `subId`를 사용합니다. 다른 연계 OJ의 문제도 solved.ac URL로 등록할 수 있습니다.

백준·DOJ·정올의 숫자 URL은 해당 OJ의 원래 문제 번호로 검색한 뒤 solved.ac 문제로 변환합니다. 해당 OJ나 문제가 solved.ac에 등록되지 않았다면 오류로 표시합니다. DOJ의 문자열 slug URL은 숫자 URL이나 solved.ac URL로 바꿔 입력합니다.

OJ 문제 하나가 여러 세부 문제로 연결된다면 등록할 세부 문제의 solved.ac URL을 입력해야 합니다. 임의로 첫 번째 문제를 선택하지 않습니다.

Codeforces·Gym·Programmers는 기존 API/HTML 수집 방식과 별도 DB를 유지합니다.

## 4. Notion DB와 기존 페이지

기존 백준 DB를 이름만 변경한 `solved.ac 데이터베이스`를 그대로 사용합니다. 기존 Data Source ID를 다음 변수에 넣습니다.

```env
NOTION_SOLVEDAC_DATA_SOURCE_ID=
```

새 변수가 비어 있으면 기존 `NOTION_BOJ_DATA_SOURCE_ID`를 사용합니다. 운영 서버의 변수 이름을 바로 바꾸지 않아도 됩니다.

Notion 속성 타입은 변경하지 않습니다.

- `문제 번호`: solved.ac의 숫자 `problemId`
- `문제 링크`: 세부 번호까지 포함한 정규 URL, 예: `https://solved.ac/p/19917a`
- `이름`, `티어`, `태그`: solved.ac에서 조회한 메타데이터
- `📚 스터디 데이터베이스`: 기존 스터디 Relation 유지

같은 숫자 번호에 `a`, `b` 등의 세부 문제가 있을 수 있으므로 문제 번호만으로 중복을 판단하지 않습니다. 문제 링크의 전체 ID를 함께 확인합니다. Discord 결과에는 세부 번호까지 표시합니다.

기존 백준 페이지는 API 응답의 `judgeIds`에 포함된 원래 백준 번호와 저장된 링크를 대조해 재사용합니다. 재등록 시 메타데이터와 아이콘만 갱신하며, 본문·학생 풀이·기존 Relation을 교체하지 않습니다. 등록할 때마다 기존 문제 전체를 일괄 변환하지 않습니다.

여러 백준 문제가 하나의 solved.ac 문제로 합쳐졌을 때 기존 Notion 페이지도 여러 개 있으면 자동 병합하지 않습니다. 어느 페이지의 풀이와 Relation을 보존할지 확인할 수 있도록 오류로 표시합니다. 기존 페이지의 링크가 없거나 해석할 수 없는 경우에도 먼저 링크를 확인하도록 안내합니다.

DOJ·정올은 기존 Notion 데이터 이동이 필요하지 않으며, 새 문제를 등록하면 같은 solved.ac DB에 저장합니다.

## 5. 기존 스터디 View 이름 변경

이후 문제 등록 시 해당 스터디의 View는 `솔브닥 N`으로 갱신됩니다.

기존 스터디들을 즉시 변경하려면 아래 스크립트를 사용합니다. 먼저 변경 대상을 확인합니다.

```bash
python scripts/rename_solvedac_views.py
```

출력된 대상에 적용합니다.

```bash
python scripts/rename_solvedac_views.py --apply
```

이 스크립트는 같은 Data Source를 사용하는 `백준`, `백준 N`, `solved.ac`, `solved.ac N` View의 이름을 `솔브닥`, `솔브닥 N`으로 바꿉니다. 필터, 정렬, 열 설정, 페이지, Relation은 수정하지 않습니다. 반복 실행해도 이미 변경된 View는 건너뜁니다.

## 6. 검증

외부 API를 호출하지 않는 회귀 테스트:

```bash
python -m pytest -q
```

실제 연동은 앱 설정 후 테스트용 문제를 `/문제등록`으로 등록해 확인합니다.

```text
[ ] solved.ac 문제 URL 등록
[ ] 기존 백준 URL로 기존 페이지 갱신
[ ] 동일 문제의 OJ URL과 solved.ac URL 중복 제거
[ ] 세부 문제 번호 보존
[ ] 스터디 Relation 보존 및 추가
[ ] solved.ac View 이름과 개수 확인
[ ] Codeforces·Programmers 기존 동작 확인
```
