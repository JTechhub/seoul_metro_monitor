import requests
from bs4 import BeautifulSoup
import json
import hashlib
from datetime import datetime
import os

class SeoulMetroMonitor:
    def __init__(self, webhook_url):
        """
        서울메트로 게시판 모니터링 클래스 (Make.com 웹훅 연동)
        
        Args:
            webhook_url (str): Make.com 웹훅 URL
        """
        self.url = "http://www.seoulmetro.co.kr/kr/board.do?menuIdx=546"
        self.webhook_url = webhook_url
        self.keywords = ["특정 장애인 단체 집회시위", "장애인", "집회", "시위"]
        self.target_date = datetime(2024, 9, 5)  # 2024년 9월 5일
        
    def fetch_board_content(self):
        """게시판 내용을 가져옴"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(self.url, headers=headers, timeout=30)
            response.encoding = 'utf-8'
            
            if response.status_code == 200:
                return response.text
            else:
                print(f"HTTP 에러: {response.status_code}")
                return None
        except Exception as e:
            print(f"웹사이트 접속 실패: {e}")
            return None
    
    def parse_board_posts(self, html_content):
        """게시판에서 게시글 정보를 파싱"""
        if not html_content:
            return []
        
        soup = BeautifulSoup(html_content, 'html.parser')
        posts = []
        
        try:
            # 다양한 테이블 구조 시도
            possible_selectors = [
                'table tr',
                '.board-list tr',
                '#board-list tr',
                'tbody tr'
            ]
            
            rows = []
            for selector in possible_selectors:
                rows = soup.select(selector)
                if rows:
                    break
            
            if not rows:
                rows = soup.find_all('tr')
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:  # 최소한 번호, 제목, 날짜는 있어야 함
                    try:
                        # 제목 추출 (보통 두 번째나 세 번째 컬럼)
                        title = ""
                        link = ""
                        
                        for i, cell in enumerate(cells):
                            cell_text = cell.get_text(strip=True)
                            # 제목으로 보이는 셀 찾기
                            if len(cell_text) > 5 and not cell_text.isdigit():
                                title = cell_text
                                # 링크 찾기
                                link_tag = cell.find('a')
                                if link_tag and link_tag.get('href'):
                                    href = link_tag['href']
                                    if not href.startswith('http'):
                                        link = "http://www.seoulmetro.co.kr" + href
                                    else:
                                        link = href
                                break
                        
                        if not title:
                            continue
                        
                        # 날짜 추출 (마지막 셀이나 날짜 형식인 셀)
                        date_str = ""
                        for cell in reversed(cells):
                            cell_text = cell.get_text(strip=True)
                            # 날짜 형식 찾기
                            if any(char in cell_text for char in ['-', '.', '/']):
                                if len(cell_text) >= 8:  # 최소 날짜 길이
                                    date_str = cell_text
                                    break
                        
                        if not date_str:
                            date_str = datetime.now().strftime('%Y-%m-%d')
                        
                        posts.append({
                            'title': title,
                            'date': date_str,
                            'link': link
                        })
                        
                    except Exception as e:
                        continue
                        
        except Exception as e:
            print(f"게시글 파싱 실패: {e}")
        
        return posts
    
    def check_keywords(self, title):
        """제목에 키워드가 포함되어 있는지 확인"""
        title_lower = title.lower()
        for keyword in self.keywords:
            if keyword.lower() in title_lower:
                return True, keyword
        return False, None
    
    def is_recent_post(self, date_str):
        """9월 5일 이후 게시글인지 확인"""
        try:
            # 다양한 날짜 형식 처리
            date_formats = [
                "%Y-%m-%d",
                "%Y.%m.%d", 
                "%m/%d/%Y",
                "%Y년 %m월 %d일",
                "%Y-%m-%d %H:%M:%S",
                "%Y.%m.%d %H:%M:%S"
            ]
            
            for fmt in date_formats:
                try:
                    post_date = datetime.strptime(date_str.split()[0], fmt)
                    return post_date >= self.target_date
                except ValueError:
                    continue
            
            # 날짜 파싱 실패시 최근 글로 간주
            print(f"날짜 형식 인식 실패: {date_str}")
            return True
            
        except Exception as e:
            print(f"날짜 확인 실패: {e}")
            return True
    
    def send_webhook(self, post_info, matched_keyword):
        """Make.com 웹훅으로 알림 전송"""
        try:
            payload = {
                'title': post_info['title'],
                'date': post_info['date'],
                'link': post_info['link'],
                'keyword': matched_keyword,
                'message': f"키워드 '{matched_keyword}' 매칭: {post_info['title']}",
                'timestamp': datetime.now().isoformat()
            }
            
            response = requests.post(
                self.webhook_url, 
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                print(f"✅ 웹훅 전송 성공: {post_info['title']}")
                return True
            else:
                print(f"❌ 웹훅 전송 실패: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 웹훅 전송 에러: {e}")
            return False
    
    def monitor_posts(self):
        """게시글 모니터링 실행"""
        print(f"🔍 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 서울메트로 게시판 모니터링 시작")
        print(f"📍 URL: {self.url}")
        print(f"🔑 키워드: {', '.join(self.keywords)}")
        
        # 웹사이트 내용 가져오기
        html_content = self.fetch_board_content()
        if not html_content:
            print("❌ 웹사이트 접속 실패")
            return
        
        # 게시글 파싱
        posts = self.parse_board_posts(html_content)
        print(f"📋 총 {len(posts)}개의 게시글 확인")
        
        if not posts:
            print("⚠️ 게시글을 찾을 수 없습니다. HTML 구조를 확인하세요.")
            return
        
        # 키워드 매칭 게시글 찾기
        notifications_sent = 0
        
        for post in posts:
            # 최근 게시글만 체크 (9월 5일 이후)
            if not self.is_recent_post(post['date']):
                continue
            
            # 키워드 체크
            has_keyword, matched_keyword = self.check_keywords(post['title'])
            if has_keyword:
                print(f"🎯 키워드 매칭 발견!")
                print(f"   제목: {post['title']}")
                print(f"   키워드: {matched_keyword}")
                print(f"   날짜: {post['date']}")
                
                # 웹훅으로 알림 전송
                if self.send_webhook(post, matched_keyword):
                    notifications_sent += 1
        
        if notifications_sent > 0:
            print(f"✅ 총 {notifications_sent}개의 알림을 전송했습니다.")
        else:
            print("📝 키워드와 매칭되는 새 게시글이 없습니다.")
        
        print("🏁 모니터링 완료\n")

# GitHub Actions 실행부
if __name__ == "__main__":
    # 환경변수에서 웹훅 URL 가져오기
    webhook_url = os.environ.get('https://hook.us2.make.com/ephh41kddl4dn6798hx2b64n8bbmrka1')
    
    if not webhook_url:
        print("❌ WEBHOOK_URL 환경변수가 설정되지 않았습니다.")
        exit(1)
    
    # 모니터링 실행
    monitor = SeoulMetroMonitor(webhook_url)
    monitor.monitor_posts()
