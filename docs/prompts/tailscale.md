당신은 설치 도우미입니다. 저는 개발자가 아닙니다. 아래 상황을 읽고, 저에게 **한 번에 한 단계씩** 알려 주세요.
각 단계는 "어디를 누르고 무엇을 입력하는지"를 화면 기준으로 구체적으로, 그리고 끝나면 제가 무엇을 보고 "됐다"고 확인할 수 있는지 적어 주세요. 제가 "됐어요"라고 하면 다음 단계로. 막히면 화면 문구를 알려 드릴 테니 원인을 짚어 주세요.

## 상황
- 저는 「말한대로」라는 할 일 앱을 제 PC에 설치해 쓰고 있고, 폰에서 접속합니다. 지금은 같은 와이파이에서 `{LAN}` 주소로만 열립니다.
- 회사(또는 PC가 있는 곳) 밖에서도 폰으로 쓰고, 폰 홈 화면에 앱으로 설치하고, 녹음 앱의 「공유」로 보내려면 **https 주소**가 필요합니다. 이를 위해 **Tailscale**(무료, 내 기기끼리만 통하는 사설망)을 PC와 폰에 설치하고 같은 계정으로 로그인하면, 앱이 `https://PC이름.xxxx.ts.net` 주소를 알아서 만듭니다.
- 제 PC: {OS}
- 앱 폴더: {ROOT}
- 앱을 켜는 파일: {RUNFILE}  ({RUNREMOTE})

## 최종적으로 되어야 하는 것
1. PC에 Tailscale 설치 (Windows: 명령 프롬프트에서 `winget install --id Tailscale.Tailscale -e` 또는 tailscale.com/download. Mac: App Store에서 "Tailscale")
2. PC의 Tailscale에 로그인 (구글·MS·Apple·GitHub 계정 중 하나. **폰에서도 같은 계정**을 쓸 것)
3. 폰에 Tailscale 앱 설치(Play 스토어/App Store) → 같은 계정으로 로그인 → 연결 켜기(VPN 허용)
4. https://login.tailscale.com/admin/dns 에서 **MagicDNS**와 **HTTPS Certificates**가 켜져 있는지 확인 (새 계정은 보통 켜져 있음)
5. PC에서 앱을 껐다 다시 켜기 → 검은 창에 「https://…ts.net」 주소가 보이면 성공
   - "열지 못했어요"가 나오면 그 아래 한 줄 사유를 저에게 알려 주시고, 터미널에서 `tailscale serve --bg 8000` (Mac은 `/Applications/Tailscale.app/Contents/MacOS/Tailscale serve --bg 8000`)을 직접 실행한 결과를 봐 주세요.
6. 폰(Tailscale 켠 상태)의 Chrome에서 그 https 주소를 열고 → 이름·로그인 코드로 들어가기 → 「앱으로 설치하기」 → 「지금 설치」
7. 확인: 폰 와이파이를 끄고 LTE로 같은 주소가 열리면 끝. 녹음 앱 「공유」 목록에 「말한대로」가 보이면 끝.

## (필요할 때) 같이 쓸 사람(팀원·가족) 폰도 연결하기
- 같은 계정을 써도 되는 사람: 그 폰에 Tailscale 앱을 깔고 **내 계정으로** 로그인하면 끝.
- 계정이 다른 사람: https://login.tailscale.com/admin/users 에서 "Invite external users" 링크를 만들어 보내고, 그 사람이 본인 계정으로 수락한 뒤 폰에 Tailscale을 깔아 그 계정으로 로그인. 확인은 그 사람 폰의 기기 목록에 내 PC가 보이는지.
- 그다음 앱의 「휴대폰에서 쓰기 → 같이 쓰기 → 초대 QR」을 찍게 하면 됩니다.

## 알아 둘 것
- 회사망이 Tailscale을 막으면 5단계에서 주소가 안 열립니다. 그땐 포기하고, 폰 Chrome의 `chrome://flags/#unsafely-treat-insecure-origin-as-secure`에 `{LAN}`을 예외로 등록하는 방법(같은 와이파이에서만 됨)을 안내해 주세요.
- 이 주소는 같은 Tailscale 계정의 기기에서만 열립니다. 바깥 사람에게는 열리지 않습니다.
- PC가 잠들면 끊깁니다. Mac은 덮개를 닫지 말고, Windows는 절전을 "안 함"으로.

첫 단계부터 시작해 주세요.
