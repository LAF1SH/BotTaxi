import json
import os
from typing import Dict, List, Optional
from datetime import datetime
import logging
from pathlib import Path


class AchievementSystem:
    def __init__(self, storage_file: str = "achievements.json"):
        self.storage_file = storage_file
        self.achievements_data: Dict[int, Dict[str, List[Dict]]] = {}
        self.available_achievements = {
            "first_login": {
                "title": "Новичок",
                "description": "Впервые авторизовался в системе",
                "icon": "🆕",
                "check_func": self._check_first_login
            },
            "top_driver": {
                "title": "Лучший водитель",
                "description": "Попасть в топ-5 водителей",
                "icon": "🏆",
                "check_func": self._check_top_driver
            },
            "workaholic": {
                "title": "Трудоголик",
                "description": "Наработать более 200 часов",
                "icon": "⏱",
                "check_func": self._check_workaholic
            },
            "high_salary": {
                "title": "Зарплатный чемпион",
                "description": "Заработать более 100,000 руб.",
                "icon": "💰",
                "check_func": self._check_high_salary
            },
            "veteran": {
                "title": "Ветеран",
                "description": "Работать более 1 года",
                "icon": "🎖",
                "check_func": self._check_veteran
            }
        }
        self.load_data()
        
    def load_data(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    self.achievements_data = json.load(f)
            except Exception as e:
                logging.error(f"Ошибка загрузки данных достижений: {e}")
                self.achievements_data = {}

    def save_data(self):
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(self.achievements_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Ошибка сохранения данных достижений: {e}")

    def _check_first_login(self, user_id: int, driver_data: Dict) -> bool:
        return not self.get_user_achievements(user_id)

    def _check_top_driver(self, user_id: int, driver_data: Dict) -> bool:
        return driver_data.get("is_in_top", False)

    def _check_workaholic(self, user_id: int, driver_data: Dict) -> bool:
        hours = float(driver_data.get("Часы", 0))
        return hours >= 200

    def _check_high_salary(self, user_id: int, driver_data: Dict) -> bool:
        salary = float(driver_data.get("ЗП", 0))
        return salary >= 100000

    def _check_veteran(self, user_id: int, driver_data: Dict) -> bool:
        # Предполагаем, что driver_data содержит дату начала работы
        start_date = driver_data.get("start_date")
        if not start_date:
            return False
        work_days = (datetime.now() - datetime.fromisoformat(start_date)).days
        return work_days >= 365

    def check_achievements(self, user_id: int, driver_data: Dict) -> List[Dict]:
        if str(user_id) not in self.achievements_data:
            self.achievements_data[str(user_id)] = {"achievements": []}
            
        new_achievements = []
        
        for achievement_id, achievement in self.available_achievements.items():
            if any(a['id'] == achievement_id for a in self.get_user_achievements(user_id)):
                continue
                
            if achievement["check_func"](user_id, driver_data):
                new_achievement = {
                    "id": achievement_id,
                    "title": achievement["title"],
                    "description": achievement["description"],
                    "icon": achievement["icon"],
                    "date": datetime.now().isoformat()
                }
                new_achievements.append(new_achievement)
                self.achievements_data[str(user_id)]["achievements"].append(new_achievement)
        
        if new_achievements:
            self.save_data()  # Сохраняем изменения сразу
        
        return new_achievements

    def get_user_achievements(self, user_id: int) -> List[Dict]:
        return self.achievements_data.get(str(user_id), {}).get("achievements", [])

    def format_achievement(self, achievement: Dict) -> str:
        return (
            f"{achievement['icon']} <b>{achievement['title']}</b>\n"
            f"{achievement['description']}\n"
            f"<i>Получено: {datetime.fromisoformat(achievement['date']).strftime('%d.%m.%Y')}</i>"
        )

    def format_achievements_list(self, achievements: List[Dict]) -> str:
        if not achievements:
            return "У вас пока нет достижений 😢\nПродолжайте работать, чтобы их получить!"
            
        message = "🏆 <b>Ваши достижения</b>:\n\n"
        for achievement in achievements:
            message += self.format_achievement(achievement) + "\n\n"
        return message
    
    def get_all_achievements_info(self, user_id: int = None) -> List[Dict]:
        """Возвращает информацию о всех достижениях с отметкой о получении"""
        user_achievements = self.get_user_achievements(user_id) if user_id else []
        achieved_ids = {a['id'] for a in user_achievements}
        
        result = []
        for ach_id, ach in self.available_achievements.items():
            ach_copy = ach.copy()
            ach_copy['id'] = ach_id
            ach_copy['achieved'] = ach_id in achieved_ids
            result.append(ach_copy)
        
        return sorted(result, key=lambda x: x['achieved'], reverse=True)

achievement_system = AchievementSystem()

def get_achievement_instance():
    return achievement_system