# PC 간 네트워크 속도 측정 도구 (iPerf3 기반)

허브/공유기로 연결된 **2대의 PC 간** 실제 전송 속도를 측정하는 Python 스크립트입니다.
측정 엔진으로는 업계 표준 벤치마크 도구인 **iPerf3**를 사용합니다.

## 목차
- [측정 개념](#측정-개념)
- [사전 준비](#사전-준비)
- [설치 (한 번만)](#설치-한-번만)
- [실행 방법](#실행-방법)
- [옵션 설명](#옵션-설명)
- [측정 원리 및 주의사항](#측정-원리-및-주의사항)
- [결과 해석](#결과-해석)
- [버그 및 문제 해결](#버그-및-문제-해결)

---

## 측정 개념

```
   [PC1] --- [허브/공유기] --- [PC2]
  (서버 모드)                (클라이언트 모드)
   접속 대기                   측정 시작
```

- **다운로드 (download)**: 서버 → 클라이언트 방향 전송 속도
- **업로드 (upload)**: 클라이언트 → 서버 방향 전송 속도
- **UDP 테스트**: 지터(Jitter, 전송 지연 편차)와 패킷 손실 측정

기본값으로 다운로드 + 업로드를 **모두** 측정합니다.

---

## 사전 준비

> 양쪽 PC 모두 아래 1~3단계를 수행하고, 방화벽(4단계)은 **서버가 되는 PC(PC1)** 에서만 수행합니다.

| 항목 | 필요한 PC | 용도 |
|------|-----------|------|
| Python 3.8+ | 양쪽 PC | 스크립트 실행 |
| Chocolatey | 양쪽 PC | iPerf3 설치 도우미 |
| iPerf3 | 양쪽 PC | 속도 측정 엔진 |
| 방화벽 규칙 | **서버 PC만** | 클라이언트의 접속 허용 |

---

### 1. Python 설치 및 확인

이 스크립트는 표준 라이브러리만 사용하므로 pip 패키지 설치는 필요 없습니다.

```powershell
# Python 설치 여부 및 버전 확인 (3.8 이상이면 통과)
python --version
```

- **없다면** [python.org](https://www.python.org/downloads/) 에서 3.12+ 설치
  - 설치 화면 맨 아래 **"Add python.exe to PATH"** 를 **반드시 체크** 후 Install
- 설치 후 명령 프롬프트를 **새로 열어** `python --version` 재확인
- `python`이 아니라 `py` 라고 입력해야 실행되는 환경이라면, 아래처럼도 동작합니다

  ```powershell
  py speed_test.py --server
  ```

---

### 2. Chocolatey 설치 (한 번만, 관리자 권한)

Chocolatey는 Windows용 패키지 관리자로, **PowerShell을 관리자 권한으로** 실행한 뒤 설치합니다.

```powershell
# 1) 관리자 권한 PowerShell 확인 (결과가 "Administrator" 여야 함)
whoami

# 2) PowerShell 실행 정책을 허용으로 변경 (Chocolatey 필수 조건)
Set-ExecutionPolicy Bypass -Scope Process -Force

# 3) Chocolatey 공식 설치 스크립트 실행
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 4) 설치 확인 (버전이 출력되면 성공)
choco --version
```

설치 흐름 상세:
1. PowerShell 시작 메뉴에서 **마우스 오른쪽 → 관리자 권한으로 실행**
2. 실행 정책이 `Restricted`면 위의 `Set-ExecutionPolicy ... -Scope Process`로 현재 세션에만 허용 (시스템 설정을 영구 변경하지 않음)
3. 설치 후 **PowerShell을 닫고 다시 관리자 권한으로** 새 세션을 열면 `choco` 명령이 인식됩니다
   - 여전히 `choco`를 찾지 못하면 새 창을 연 뒤 다음을 실행:

   ```powershell
   $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
   ```

- **이미 설치되어 있는지 확인**: `choco --version`이 버전을 출력하면 다음 단계로 이동
- Chocolatey를 못 쓸 때의 대안은 아래 [iPerf3 수동 설치](#iperf3-수동-설치-대안) 참고

---

### 3. iPerf3 설치 (한 번만)

Chocolatey 설치가 끝나면 **새 관리자 PowerShell**에서 아래 명령으로 설치합니다.

```powershell
# Chocolatey로 iPerf3 설치 (이미 있으면 최신 버전 유지)
choco install iperf3 -y --no-progress

# 설치 확인 (아래처럼 버전 정보가 출력되면 성공)
iperf3 --version
# 예: iperf 3.20 (cJSON 1.7.15)
```

설치 상세:
- 설치 위치: `C:\ProgramData\chocolatey\lib\iperf3\tools\`
- `iperf3` 실행 파일은 Chocolatey가 PATH에 자동 등록하지만, **설치 전에 열어둔 셸에서는 인식되지 않습니다.** 셸을 새로 열어 확인하세요.
- 설치 실패 시(hash 검증 등) 아래 명령으로 재시도:

  ```powershell
  choco install iperf3 -y --force --no-progress
  ```

- 동일한 요사를 해소한 뒤에도 `iperf3`가 실행되지 않으면:

  ```powershell
  where.exe iperf3
  ```

  경로가 출력되면 그 경로를 직접 사용해도 됩니다. 예: `& "C:\ProgramData\chocolatey\lib\iperf3\tools\iperf3\iperf3.exe" --version`

#### iPerf3 수동 설치 (대안)

아래 경로 중 편한 방법으로 설치해도 됩니다. 설치 후 `perf3.exe`가 PATH에 있어야 스크립트가 동작합니다.

| 방법 | 명령 (관리자 PowerShell) |
|------|--------------------------|
| **winget** (Windows 10/11 기본) | `winget install -e --id iperf3.Iperf3` |
| **직접 다운로드** | iPerf3 공식 다운로드 페이지에서 Windows 64-bit zip을 받아 `C:\iperf3` 등에 압축 해제 후, 그 폴더를 PATH에 추가 |

winget의 경우 배포처명이 위와 다를 수 있으니 `winget search iperf3`로 확인하세요.

---

### 4. 방화벽 허용 (서버 PC만, 한 번만)

클라이언트 PC가 서버 PC의 포트 **5201**에 접속할 수 있도록 방화벽에 규칙을 추가합니다.
**서버가 되는 PC(PC1)** 에서 **관리자 PowerShell**로 실행합니다.

```powershell
# TCP(In): 속도 측정 메인 데이터 전송
netsh advfirewall firewall add rule name="iperf3" dir=in action=allow protocol=TCP localport=5201

# UDP(In): UDP 테스트(지터/패킷 손실) 통과
netsh advfirewall firewall add rule name="iperf3-udp" dir=in action=allow protocol=UDP localport=5201
```

- 다른 포트를 사용하려면 `--port 9000` 처럼 지정한 포트 번호로 위 `localport=...` 값을 바꾸면 됩니다.
- 실행 후 **등록 확인**:

  ```powershell
  netsh advfirewall firewall show rule name="iperf3"
  netsh advfirewall firewall show rule name="iperf3-udp"
  ```

- **삭제 방법** (설정 변경 시):

  ```powershell
  netsh advfirewall firewall delete rule name="iperf3"
  netsh advfirewall firewall delete rule name="iperf3-udp"
  ```

- **GUI로 하려면**: `Windows 보안 → 방화벽 및 네트워크 보호 → 고급 설정 → 인바운드 규칙 → 새 규칙`에서
  포트 `5201`(TCP/UDP) 인바운드 허용으로 추가

> 방화벽 규칙을 추가했는데도 접속이 안 되면, 사설(개인) 네트워크 프로필이 지금 연결된 네트워크에 적용되는지도 확인하세요.

#### 접속 가능 여부 미리 확인 (같은 네트워크에서)

서버 PC에서 서버 모드를 실행한 뒤, **클라이언트 PC**의 PowerShell에서:

```powershell
Test-NetConnection 192.168.1.100 -Port 5201
```

- `TcpTestSucceeded : True` → 서버 접속 성공
- `False` → 방화벽 규칙, IP, 서버 실행 여부 점검

---

### 5. IP 확인 및 네트워크 구성 (장치 준비)

양쪽 PC에서 각각 IP를 확인합니다.

```powershell
# 방법 1: ipconfig 로 직접 확인
ipconfig
#    IPv4 주소 . . . . : 192.168.1.100   ← 이 값이 상대 PC가 접속할 주소

# 방법 2: 이 스크립트의 --show-ip 로 확인
python speed_test.py --show-ip
```

**같은 서브넷 확인** — 두 PC의 IPv4 주소 앞 3자리(네트워크 부분)가 같아야 합니다.

| PC | IPv4 주소 | 서브넷(네트워크부) |
|----|-----------|---------------------|
| PC1 | 192.168.**0**.100 | 192.168.0.x |
| PC2 | 192.168.**0**.101 | 192.168.0.x |

- 같은 공유기/허브 아래에 연결돼 있으면 대부분 같습니다.
- 서브넷이 다르면(예: 192.168.0.x / 192.168.123.x) 라우팅 문제가 있어 상호 접속이 안 될 수 있습니다.
- 참고: `169.254.x.x` 는 **DHCP IP를 못 받은 상태**(APIPA)로, 정상 IP가 아닙니다. 유선 연결 및 DHCP 확인 필요. `172.x.x.x`, `192.168.x.x`, `10.x.x.x` 가 일반적인 내부 IP입니다.

**연결 자체가 되는지 ping 확인** (클라이언트 PC에서):

```powershell
ping 192.168.1.100
```

- 응답이 오면 회선은 정상 → 바로 [실행 방법](#실행-방법) 진행
- `요청 시간이 만료되었습니다` 라고 나와도 양쪽 PC가 방화벽으로 ping을 차단하고 있을 수 있으므로 속도 측정이 불가능한 것은 아닙니다.

---

## 설치 (한 번만)

```powershell
# 스크립트에 필요한 것은 Python 3.8+ 과 iPerf3 뿐입니다.
# 별도의 pip 패키지는 필요 없습니다 (표준 라이브러리만 사용).
python --version   # 3.8 이상 확인
iperf3 --version   # 설치 확인
```

---

## 실행 방법

> **항상 먼저 서버 모드를 실행**한 뒤, 클라이언트 모드를 실행합니다.

### 1단계 — PC1에서 서버 모드 실행

```bash
python speed_test.py --server
```

부팅 후 자동 실행이 필요하면 Windows 작업 스케줄러에 아래 명령을 등록하면 됩니다.

```powershell
python C:\Users\Administrator\Desktop\speed_test\speed_test.py --server
```

> 참고: 서버 모드는 `Ctrl+C` 로 종료됩니다.

### 2단계 — PC2에서 클라이언트 모드 실행

```bash
# 기본: 다운로드 + 업로드, 각 10초
python speed_test.py --client 192.168.1.100

# 60초 동안 4개의 병렬 스트림으로 테스트
python speed_test.py --client 192.168.1.100 --duration 60 --parallel 4

# UDP 테스트 (지터/패킷 손실)
python speed_test.py --client 192.168.1.100 --udp --bandwidth 100M

# TCP + UDP 모두, 3회 반복, 결과 CSV 저장
python speed_test.py --client 192.168.1.100 --udp --times 3 --output result.csv

# 업로드만 측정
python speed_test.py --client 192.168.1.100 --direction upload
```

### 서버 종료

서버 PC에서 `Ctrl+C` 를 누르면 종료됩니다.

---

## 옵션 설명

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--server` | - | 서버 모드로 실행 (수신 대기) |
| `--client HOST` | - | 클라이언트 모드, 상대 PC IP |
| `--port PORT` | `5201` | 사용 포트 |
| `--duration N` | `10` | 테스트 시간(초) |
| `--parallel N` | `1` | 병렬 스트림 수 |
| `--udp` | off | UDP 테스트 (지터/손실 측정) |
| `--bandwidth B` | `100M` | UDP 타깃 대역폭 (K/M/G 접두사, 예: 500M, 1G) |
| `--times N` | `1` | 반복 측정 횟수 |
| `--direction` | `both` | `download` / `upload` / `both` |
| `--output CSV` | - | 결과를 CSV 파일로 저장 |
| `--show-ip` | - | 현재 PC IP 표시 후 종료 |
| `--help` | - | 도움말 표시 |

---

## 측정 원리 및 주의사항

### 허브를 통한 측정이란?
- **허브**는 반이중(동시에 한 방향만) 방식이라 다운로드/업로드를 동시에 수행하면 정확도가 떨어집니다.
- 반드시 **한 방향씩** 측정하세요. (이 도구는 기본적으로 방향별 순차 측정)
- 스위치/공유기 사용 시 각 PC는 전용 대역폭을 사용하므로 더 정확합니다.

### 측정 시 유의점
1. **구리 케이블/연결이 100Mbps 인터페이스**면 100Mbps가 물리적 한계입니다.
2. 네트워크를 사용하는 다른 프로그램(다운로드, 스트리밍 등)을 종료하세요.
3. 와이파이보다 **유선(랜케이블)이 더 안정적**입니다.
4. Windows Defender 등 보안 프로그램은 속도에 영향을 줄 수 있습니다.
5. 서버 모드 시작 후 몇 초 후 클라이언트를 실행하세요.

### 대역폭 단위
- 결과는 초당 **메가비트(Mbps)** 단위로 표시됩니다.
- `1 Mbps = 1,000,000 bits/sec` (10진법 단위)
- 다운로드 속도 표기(예: 100Mbps)와 파일 크기(MB/s)를 혼동하지 마세요:
  - `100 Mbps ÷ 8 = 12.5 MB/s` (실제 파일 전송 속도)

---

## 결과 해석

실행 예:

```
+------------------+------------+------------+------------+------------+----------+
| 측정 항목        |   평균 Mbps |   최소 Mbps |   최대 Mbps |    지터 ms |   손실 % |
+------------------+------------+------------+------------+------------+----------+
| TCP download ... |     941.20 |     912.45 |     980.30 |          - |        - |
| TCP upload   ... |     905.38 |     880.12 |     933.77 |          - |        - |
| UDP upload   ... |     99.87  |     99.01  |     100.02 |      0.512 |     0.01 |
+------------------+------------+------------+------------+------------+----------+
TCP 재전송 패킷 수 (업로드 제외 누계): 12
```

| 지표 | 의미 |
|------|------|
| 평균/최소/최대 Mbps | 순간 속도의 구간별 집계 (Mbits/s) |
| 지터 (ms) | 전송 지연의 일관성. 낮을수록 좋음 (UDP 전용) |
| 손실 (%) | 보낸 패킷 중 잃어버린 비율. 0%가 정상 (UDP 전용) |
| 재전송 수 | TCP로 재전송된 패킷 수. 많으면 회선 품질 문제 |

- 기가비트(1000BASE-T) 환경이면 대략 **900~990 Mbps** 수준이 정상입니다.
- 100Mbps(100BASE-TX) 환경이면 대략 **90~99 Mbps** 수준입니다.
- 값이 현저히 낮으면 케이블, 허브(반이중), 간섭, 드라이버 설정을 점검하세요.

### UDP 손실/지터 기준
- 손실 `0%` 이상이면 VoIP(인터넷 전화), 온라인 게임에 영향 가능
- 지터 30ms 초과 시 실시간 통신 품질 저하

---

## 버그 및 문제 해결

| 증상 | 해결 방법 |
|------|-----------|
| `unable to connect` | 서버 PC에서 서버 모드 실행 여부 확인, 방화벽 허용, IP/포트 확인 |
| `iperf3 실행 파일을 찾을 수 없습니다` | `choco install iperf3 -y` 실행 후 셸 재시작 |
| 방화벽 차단 | `netsh advfirewall ...` 규칙 추가 (사전 준비 참조) |
| 결과가 낮게 나옴 | 다른 트래픽 종료, 유선 연결 확인, 허브 → 스위치 교체 고려 |
| 파이썬 버전 문제 | Python 3.8+ 필요 (`python --version`) |

### 파일 구조

```
Desktop/speed_test/
├── speed_test.py    # 메인 스크립트
└── README.md        # 이 문서
```