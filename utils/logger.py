"""
日志记录器，负责记录游戏过程中的所有信息

主要职责：
1. 日志记录
   - 记录游戏流程
   - 记录玩家行为
   - 记录 AI 响应
   - 记录系统事件
   - 记录模型评估指标

2. 日志格式化
   - 控制台输出格式
   - 文件记录格式
   - 不同级别日志区分
   - 评估指标统计

3. 日志管理
   - 日志轮转（按大小和时间）
   - 分级存储（DEBUG/INFO/ERROR）
   - 自动清理旧日志
   - 日志压缩归档

4. 与其他模块的交互：
   - 被所有模块调用记录日志
   - 管理 logs 目录
   - 支持日志回放功能
   - 生成评估报告

类设计：
class GameLogger:
    def __init__(self, debug: bool = False)
    def log_round()
    def log_event()
    def log_game_over()
    def save_game_record()
"""

import logging
import logging.handlers
import os
import gzip
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json
import csv
import glob
from pathlib import Path


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""
    
    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
        'RESET': '\033[0m'        # 重置
    }
    
    def format(self, record):
        # 保存原始级别名称
        original_levelname = record.levelname
        
        # 添加颜色（仅控制台）
        if hasattr(self, '_is_console') and self._is_console:
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        
        result = super().format(record)
        
        # 恢复原始级别名称
        record.levelname = original_levelname
        return result


class GameLogger:
    """游戏日志记录器"""
    
    # 日志保留配置
    LOG_RETENTION_DAYS = 7  # 日志保留天数
    MAX_LOG_SIZE_MB = 10    # 单个日志文件最大大小（MB）
    MAX_BACKUP_COUNT = 5    # 备份文件数量
    
    def __init__(self, debug: bool = False, log_dir: str = 'logs'):
        self.debug = debug
        self.log_dir = log_dir
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 游戏记录数据
        self.game_record = {
            "start_time": datetime.now().isoformat(),
            "rounds": [],
            "events": [],
            "final_result": None,
            "model_metrics": {},
            "game_stats": {
                "total_rounds": 0,
                "total_deaths": 0,
                "ability_uses": 0,
                "votes": []
            },
            "round_records": []
        }
        
        # 初始化
        self._setup_directories()
        self._cleanup_old_logs()
        self._setup_logger()
        self._init_metrics()
    
    def _setup_directories(self):
        """创建必要的目录"""
        directories = [
            self.log_dir,
            f'{self.log_dir}/archive',
            'test_analysis',
            'game_results',
            'game_stats'
        ]
        for dir_name in directories:
            Path(dir_name).mkdir(parents=True, exist_ok=True)
    
    def _cleanup_old_logs(self):
        """清理旧日志文件"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.LOG_RETENTION_DAYS)
            log_path = Path(self.log_dir)
            
            for log_file in log_path.glob('*.log'):
                if log_file.is_file():
                    file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if file_mtime < cutoff_date:
                        # 压缩旧日志
                        archive_path = log_path / 'archive' / f"{log_file.name}.gz"
                        with open(log_file, 'rb') as f_in:
                            with gzip.open(archive_path, 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        # 删除原文件
                        log_file.unlink()
                        logging.info(f"已归档旧日志: {log_file.name}")
            
            # 清理旧归档文件
            archive_path = log_path / 'archive'
            if archive_path.exists():
                for archive_file in archive_path.glob('*.gz'):
                    file_mtime = datetime.fromtimestamp(archive_file.stat().st_mtime)
                    if file_mtime < cutoff_date - timedelta(days=7):  # 归档文件多保留7天
                        archive_file.unlink()
                        
        except Exception as e:
            print(f"清理旧日志时出错: {e}")
    
    def _setup_logger(self):
        """设置日志系统"""
        # 日志格式
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # 彩色格式化器（用于控制台）
        console_formatter = ColoredFormatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_formatter._is_console = True
        
        # 获取根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
        
        # 清除现有处理器
        root_logger.handlers.clear()
        
        # 1. 游戏主日志（按大小轮转）
        game_log_path = f'{self.log_dir}/game_{self.timestamp}.log'
        game_handler = logging.handlers.RotatingFileHandler(
            game_log_path,
            maxBytes=self.MAX_LOG_SIZE_MB * 1024 * 1024,
            backupCount=self.MAX_BACKUP_COUNT,
            encoding='utf-8'
        )
        game_handler.setFormatter(detailed_formatter)
        game_handler.setLevel(logging.INFO)
        root_logger.addHandler(game_handler)
        
        # 2. 调试日志（详细记录）
        debug_log_path = f'{self.log_dir}/debug_{self.timestamp}.log'
        debug_handler = logging.handlers.RotatingFileHandler(
            debug_log_path,
            maxBytes=self.MAX_LOG_SIZE_MB * 1024 * 1024,
            backupCount=self.MAX_BACKUP_COUNT,
            encoding='utf-8'
        )
        debug_handler.setFormatter(detailed_formatter)
        debug_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(debug_handler)
        
        # 3. 错误日志（仅记录错误）
        error_log_path = f'{self.log_dir}/error_{self.timestamp}.log'
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_path,
            maxBytes=self.MAX_LOG_SIZE_MB * 1024 * 1024,
            backupCount=self.MAX_BACKUP_COUNT,
            encoding='utf-8'
        )
        error_handler.setFormatter(detailed_formatter)
        error_handler.setLevel(logging.ERROR)
        root_logger.addHandler(error_handler)
        
        # 4. 控制台输出
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)
        
        # 记录启动信息
        logging.info("=" * 50)
        logging.info("🎮 AI狼人杀游戏日志系统启动")
        logging.info("=" * 50)
        logging.info(f"📅 时间戳: {self.timestamp}")
        logging.info(f"🐛 调试模式: {'开启' if self.debug else '关闭'}")
        logging.info(f"📝 日志目录: {self.log_dir}")
        logging.info(f"📦 日志保留: {self.LOG_RETENTION_DAYS}天")
        logging.info("=" * 50)
    
    def _init_metrics(self):
        """初始化评估指标"""
        self.metrics = {
            "role_recognition": {"correct": 0, "total": 0},
            "deception_success": {"successful": 0, "attempts": 0},
            "voting_accuracy": {"correct": 0, "total": 0},
            "communication_effect": {"influential_messages": 0, "total_messages": 0},
            "survival_rate": {"rounds_survived": 0, "total_rounds": 0},
            "ability_usage": {"correct": 0, "total": 0},
            "vote_validity": {
                "valid_votes": 0,
                "total_votes": 0,
                "player_stats": {}
            }
        }
    
    # ==================== 日志记录方法 ====================
    
    def log_role_recognition(self, player_id: str, is_correct: bool):
        """记录角色识别准确率"""
        self.metrics["role_recognition"]["total"] += 1
        if is_correct:
            self.metrics["role_recognition"]["correct"] += 1
        
        status = "✅ 正确" if is_correct else "❌ 错误"
        logging.debug(f"角色识别: 玩家{player_id} {status}")
        
        self.game_record["events"].append({
            "type": "role_recognition",
            "player_id": player_id,
            "is_correct": is_correct,
            "timestamp": datetime.now().isoformat()
        })
    
    def log_deception_attempt(self, player_id: str, is_successful: bool):
        """记录欺骗成功率"""
        self.metrics["deception_success"]["attempts"] += 1
        if is_successful:
            self.metrics["deception_success"]["successful"] += 1
        
        status = "✅ 成功" if is_successful else "❌ 失败"
        logging.debug(f"欺骗尝试: 玩家{player_id} {status}")
        
        self.game_record["events"].append({
            "type": "deception_attempt",
            "player_id": player_id,
            "is_successful": is_successful,
            "timestamp": datetime.now().isoformat()
        })
    
    def log_vote(self, voter_id: str, target_id: str, is_correct: bool):
        """记录投票准确率"""
        self.metrics["voting_accuracy"]["total"] += 1
        if is_correct:
            self.metrics["voting_accuracy"]["correct"] += 1
        
        status = "✅" if is_correct else "❌"
        logging.info(f"{status} 投票记录: {voter_id} → {target_id}")
        
        self.game_record["game_stats"]["votes"].append({
            "voter_id": voter_id,
            "target_id": target_id,
            "is_correct": is_correct,
            "round": self.game_record["game_stats"]["total_rounds"],
            "timestamp": datetime.now().isoformat()
        })
    
    def log_communication(self, player_id: str, message_id: str, influenced_others: bool):
        """记录沟通效果"""
        self.metrics["communication_effect"]["total_messages"] += 1
        if influenced_others:
            self.metrics["communication_effect"]["influential_messages"] += 1
        
        status = "🎯 有影响" if influenced_others else "💬 无影响"
        logging.debug(f"沟通: 玩家{player_id}的消息 {status}")
    
    def log_survival(self, player_id: str, rounds_survived: int, total_rounds: int):
        """记录生存率"""
        self.metrics["survival_rate"]["rounds_survived"] += rounds_survived
        self.metrics["survival_rate"]["total_rounds"] += total_rounds
        logging.debug(f"生存: 玩家{player_id} 存活{rounds_survived}/{total_rounds}轮")
    
    def log_ability_usage(self, player_id: str, ability_type: str, is_correct: bool):
        """记录能力使用准确率"""
        self.metrics["ability_usage"]["total"] += 1
        if is_correct:
            self.metrics["ability_usage"]["correct"] += 1
        
        self.game_record["game_stats"]["ability_uses"] += 1
        status = "✅" if is_correct else "❌"
        logging.info(f"{status} 能力使用: {player_id} 使用 {ability_type}")
    
    def log_vote_validity(self, player_id: str, is_valid: bool, reason: str = None):
        """记录投票有效性"""
        self.metrics["vote_validity"]["total_votes"] += 1
        if is_valid:
            self.metrics["vote_validity"]["valid_votes"] += 1
        
        # 更新玩家统计
        if player_id not in self.metrics["vote_validity"]["player_stats"]:
            self.metrics["vote_validity"]["player_stats"][player_id] = {
                "valid_votes": 0,
                "total_votes": 0,
                "invalid_reasons": {}
            }
        
        player_stats = self.metrics["vote_validity"]["player_stats"][player_id]
        player_stats["total_votes"] += 1
        if is_valid:
            player_stats["valid_votes"] += 1
        elif reason:
            player_stats["invalid_reasons"][reason] = player_stats["invalid_reasons"].get(reason, 0) + 1
        
        if not is_valid:
            logging.warning(f"⚠️  无效投票: {player_id} - {reason}")
    
    def log_round(self, round_num: int, phase: str, events: List[Dict]):
        """记录每个回合的信息"""
        round_record = {
            "round_number": round_num,
            "phase": phase,
            "events": events,
            "timestamp": datetime.now().isoformat()
        }
        self.game_record["rounds"].append(round_record)
        self.game_record["game_stats"]["total_rounds"] = round_num
        
        logging.info("")
        logging.info("═" * 50)
        logging.info(f"🔄 第 {round_num} 回合 {phase} 阶段")
        logging.info("═" * 50)
        for event in events:
            logging.info(f"  📌 {event}")
    
    def log_event(self, event_type: str, details: Dict[str, Any]):
        """记录游戏事件"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            **details
        }
        self.game_record["events"].append(event)
        
        # 特殊事件处理
        if event_type == "death":
            self.game_record["game_stats"]["total_deaths"] += 1
            logging.info(f"💀 玩家死亡: {details.get('player_id', '未知')}")
        elif event_type == "kill":
            logging.info(f"🗡️  夜间击杀: {details.get('target_id', '未知')}")
        elif event_type == "save":
            logging.info(f"💊 女巫救人: {details.get('target_id', '未知')}")
        elif event_type == "poison":
            logging.info(f"☠️  女巫毒杀: {details.get('target_id', '未知')}")
        elif event_type == "check":
            logging.info(f"🔍 预言家查验: {details.get('target_id', '未知')}")
        elif event_type == "shoot":
            logging.info(f"🔫 猎人开枪: {details.get('target_id', '未知')}")
        else:
            logging.info(f"📋 游戏事件: {event_type} - {details}")
    
    def log_round_discussion(self, round_num: int, discussions: List[Dict]):
        """记录每轮的讨论内容"""
        self._add_to_round_record(round_num, "discussions", discussions)
        
        logging.info("")
        logging.info("🗣️  讨论记录:")
        for disc in discussions:
            player = disc.get('player', '未知')
            content = disc.get('content', '')[:100]  # 只显示前100字符
            logging.info(f"  💬 {player}: {content}...")
    
    def log_round_vote(self, round_num: int, vote_results: Dict):
        """记录每轮的投票结果"""
        self._add_to_round_record(round_num, "vote_results", vote_results)
        
        logging.info("")
        logging.info("🗳️  投票结果:")
        for player_id, votes in vote_results.get("vote_counts", {}).items():
            player_name = vote_results.get("player_names", {}).get(player_id, player_id)
            logging.info(f"  • {player_name}: {votes} 票")
        
        if vote_results.get("is_tie"):
            logging.info("⚖️  出现平票，随机选择")
        
        voted_out = vote_results.get("voted_out_name", "未知")
        logging.info(f"  🚫 被投出: {voted_out}")
    
    def _add_to_round_record(self, round_num: int, record_type: str, data: Any):
        """添加数据到轮次记录"""
        round_record = None
        for record in self.game_record["round_records"]:
            if record["round"] == round_num:
                round_record = record
                break
        
        if round_record is None:
            round_record = {
                "round": round_num,
                "timestamp": datetime.now().isoformat()
            }
            self.game_record["round_records"].append(round_record)
        
        round_record[record_type] = data
    
    # ==================== 游戏结束处理 ====================
    
    def log_game_over(self, winner: str, final_state: Dict[str, Any]):
        """记录游戏结束信息"""
        metrics = self.calculate_metrics()
        
        self.game_record["final_result"] = {
            "winner": winner,
            "final_state": final_state,
            "end_time": datetime.now().isoformat(),
            "metrics": metrics,
            "game_stats": self.game_record["game_stats"]
        }
        
        # 输出游戏结束信息
        logging.info("")
        logging.info("=" * 50)
        logging.info("🏁 游戏结束")
        logging.info("=" * 50)
        logging.info(f"🎉 胜利方: {winner}")
        logging.info("")
        logging.info("📊 游戏统计:")
        logging.info(f"  • 总回合数: {self.game_record['game_stats']['total_rounds']}")
        logging.info(f"  • 总死亡数: {self.game_record['game_stats']['total_deaths']}")
        logging.info(f"  • 技能使用次数: {self.game_record['game_stats']['ability_uses']}")
        logging.info("")
        logging.info("📈 评估指标:")
        for metric_name, value in metrics.items():
            if isinstance(value, float):
                logging.info(f"  • {metric_name}: {value:.2%}")
        logging.info("=" * 50)
        
        # 保存记录
        self.save_game_record()
        self._generate_analysis_report()
    
    def calculate_metrics(self) -> Dict[str, float]:
        """计算最终评估指标"""
        results = {}
        
        # 角色识别准确率
        if self.metrics["role_recognition"]["total"] > 0:
            results["role_recognition_accuracy"] = (
                self.metrics["role_recognition"]["correct"] / 
                self.metrics["role_recognition"]["total"]
            )
        
        # 欺骗成功率
        if self.metrics["deception_success"]["attempts"] > 0:
            results["deception_success_rate"] = (
                self.metrics["deception_success"]["successful"] / 
                self.metrics["deception_success"]["attempts"]
            )
        
        # 投票准确率
        if self.metrics["voting_accuracy"]["total"] > 0:
            results["voting_accuracy"] = (
                self.metrics["voting_accuracy"]["correct"] / 
                self.metrics["voting_accuracy"]["total"]
            )
        
        # 沟通效果
        if self.metrics["communication_effect"]["total_messages"] > 0:
            results["communication_effectiveness"] = (
                self.metrics["communication_effect"]["influential_messages"] / 
                self.metrics["communication_effect"]["total_messages"]
            )
        
        # 生存率
        if self.metrics["survival_rate"]["total_rounds"] > 0:
            results["survival_rate"] = (
                self.metrics["survival_rate"]["rounds_survived"] / 
                self.metrics["survival_rate"]["total_rounds"]
            )
        
        # 能力使用准确率
        if self.metrics["ability_usage"]["total"] > 0:
            results["ability_usage_accuracy"] = (
                self.metrics["ability_usage"]["correct"] / 
                self.metrics["ability_usage"]["total"]
            )
        
        # 投票有效率
        if self.metrics["vote_validity"]["total_votes"] > 0:
            results["vote_validity_rate"] = (
                self.metrics["vote_validity"]["valid_votes"] / 
                self.metrics["vote_validity"]["total_votes"]
            )
        
        return results
    
    def save_game_record(self):
        """保存完整的游戏记录"""
        # 保存详细游戏记录
        record_file = f'{self.log_dir}/game_record_{self.timestamp}.json'
        with open(record_file, 'w', encoding='utf-8') as f:
            json.dump(self.game_record, f, ensure_ascii=False, indent=2)
        
        logging.info(f"💾 游戏记录已保存: {record_file}")
        
        # 保存简要统计
        stats_file = f'test_analysis/game_stats_{self.timestamp}.json'
        stats = {
            "timestamp": self.timestamp,
            "metrics": self.game_record["final_result"]["metrics"],
            "game_stats": self.game_record["game_stats"],
            "winner": self.game_record["final_result"]["winner"]
        }
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        # 记录结果
        self.log_game_result()
        self.log_multi_game_stats()
    
    def log_game_result(self):
        """记录单局游戏结果到CSV"""
        csv_file = f'game_results/game_result_{self.timestamp}.csv'
        
        final_result = self.game_record.get("final_result", {})
        winner = final_result.get("winner", "未知")
        metrics = final_result.get("metrics", {})
        
        # 获取玩家数据
        players_data = []
        if "final_state" in final_result and "players" in final_result["final_state"]:
            for player_id, player_info in final_result["final_state"]["players"].items():
                ai_model = player_info.get("ai_model", "未知")
                role = player_info.get("role", "未知")
                is_alive = player_info.get("is_alive", False)
                
                is_winner = False
                if (winner == "狼人阵营" and role == "werewolf") or \
                   (winner == "好人阵营" and role != "werewolf"):
                    is_winner = True
                
                players_data.append({
                    "player_id": player_id,
                    "name": player_info.get("name", player_id),
                    "role": role,
                    "ai_model": ai_model,
                    "is_alive": is_alive,
                    "is_winner": is_winner
                })
        
        # 写入CSV
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                "game_id", "timestamp", "winner", "total_rounds", 
                "player_id", "player_name", "role", "ai_model", "is_alive", "is_winner",
                "role_recognition_accuracy", "deception_success_rate", "voting_accuracy",
                "communication_effectiveness", "survival_rate", "ability_usage_accuracy"
            ]
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            game_id = f"game_{self.timestamp}"
            for player in players_data:
                row = {
                    "game_id": game_id,
                    "timestamp": self.timestamp,
                    "winner": winner,
                    "total_rounds": self.game_record["game_stats"]["total_rounds"],
                    "player_id": player["player_id"],
                    "player_name": player["name"],
                    "role": player["role"],
                    "ai_model": player["ai_model"],
                    "is_alive": "是" if player["is_alive"] else "否",
                    "is_winner": "是" if player["is_winner"] else "否"
                }
                
                for metric_name, value in metrics.items():
                    if metric_name in fieldnames:
                        row[metric_name] = value
                
                writer.writerow(row)
        
        logging.info(f"📊 单局结果已保存: {csv_file}")
    
    def log_multi_game_stats(self):
        """记录多轮游戏统计到CSV"""
        game_result_files = glob.glob('game_results/game_result_*.csv')
        
        if not game_result_files:
            logging.warning("没有找到单局游戏结果文件")
            return
        
        # 统计模型数据
        model_stats = {}
        
        for result_file in game_result_files:
            with open(result_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ai_model = row.get("ai_model", "未知")
                    role = row.get("role", "未知")
                    is_winner = row.get("is_winner", "否") == "是"
                    is_alive = row.get("is_alive", "否") == "是"
                    
                    if ai_model not in model_stats:
                        model_stats[ai_model] = {
                            "total_games": 0, "wins": 0,
                            "werewolf_games": 0, "werewolf_wins": 0,
                            "villager_games": 0, "villager_wins": 0,
                            "survival_count": 0,
                            "metrics": {m: [] for m in [
                                "role_recognition_accuracy", "deception_success_rate",
                                "voting_accuracy", "communication_effectiveness",
                                "survival_rate", "ability_usage_accuracy"
                            ]}
                        }
                    
                    stats = model_stats[ai_model]
                    stats["total_games"] += 1
                    if is_winner:
                        stats["wins"] += 1
                    
                    if role == "werewolf":
                        stats["werewolf_games"] += 1
                        if is_winner:
                            stats["werewolf_wins"] += 1
                    else:
                        stats["villager_games"] += 1
                        if is_winner:
                            stats["villager_wins"] += 1
                    
                    if is_alive:
                        stats["survival_count"] += 1
                    
                    for metric_name in stats["metrics"]:
                        if metric_name in row and row[metric_name]:
                            try:
                                stats["metrics"][metric_name].append(float(row[metric_name]))
                            except (ValueError, TypeError):
                                pass
        
        # 写入CSV
        csv_file = f'game_stats/multi_game_stats_{self.timestamp}.csv'
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                "AI模型", "总场次", "总胜场", "总胜率", 
                "狼人场次", "狼人胜场", "狼人胜率",
                "好人场次", "好人胜场", "好人胜率",
                "存活率", "角色识别准确率", "欺骗成功率", 
                "投票准确率", "沟通效果", "能力使用准确率"
            ]
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for model, stats in model_stats.items():
                win_rate = stats["wins"] / stats["total_games"] if stats["total_games"] > 0 else 0
                werewolf_win_rate = stats["werewolf_wins"] / stats["werewolf_games"] if stats["werewolf_games"] > 0 else 0
                villager_win_rate = stats["villager_wins"] / stats["villager_games"] if stats["villager_games"] > 0 else 0
                survival_rate = stats["survival_count"] / stats["total_games"] if stats["total_games"] > 0 else 0
                
                avg_metrics = {}
                for metric_name, values in stats["metrics"].items():
                    avg_metrics[metric_name] = sum(values) / len(values) if values else 0
                
                writer.writerow({
                    "AI模型": model,
                    "总场次": stats["total_games"],
                    "总胜场": stats["wins"],
                    "总胜率": win_rate,
                    "狼人场次": stats["werewolf_games"],
                    "狼人胜场": stats["werewolf_wins"],
                    "狼人胜率": werewolf_win_rate,
                    "好人场次": stats["villager_games"],
                    "好人胜场": stats["villager_wins"],
                    "好人胜率": villager_win_rate,
                    "存活率": survival_rate,
                    "角色识别准确率": avg_metrics.get("role_recognition_accuracy", 0),
                    "欺骗成功率": avg_metrics.get("deception_success_rate", 0),
                    "投票准确率": avg_metrics.get("voting_accuracy", 0),
                    "沟通效果": avg_metrics.get("communication_effectiveness", 0),
                    "能力使用准确率": avg_metrics.get("ability_usage_accuracy", 0)
                })
        
        logging.info(f"📈 多轮统计已保存: {csv_file}")
    
    def _generate_analysis_report(self):
        """生成分析报告"""
        report_file = f'test_analysis/analysis_report_{self.timestamp}.txt'
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("🐺 AI狼人杀游戏分析报告\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"📅 游戏时间: {self.game_record['start_time']}\n")
            f.write(f"⏱️  游戏时长: {self.game_record['game_stats']['total_rounds']} 回合\n\n")
            
            # 每轮详细记录
            f.write("=" * 60 + "\n")
            f.write("📜 每轮详细记录\n")
            f.write("=" * 60 + "\n\n")
            
            for round_record in self.game_record["round_records"]:
                round_num = round_record["round"]
                f.write(f"\n第 {round_num} 回合\n")
                f.write("-" * 40 + "\n")
                
                if "discussions" in round_record:
                    f.write("\n🗣️ 讨论内容:\n")
                    for disc in round_record["discussions"]:
                        f.write(f"\n{disc['player']}:\n")
                        content = disc.get('content', '')
                        # 格式化长文本
                        for line in content.split('\n'):
                            f.write(f"  {line}\n")
                
                if "vote_results" in round_record:
                    f.write("\n🗳️ 投票结果:\n")
                    vote_results = round_record["vote_results"]
                    for player_id, votes in vote_results["vote_counts"].items():
                        player_name = vote_results.get("player_names", {}).get(player_id, player_id)
                        f.write(f"  • {player_name}: {votes} 票\n")
                        voters = [v["voter_name"] for v in vote_results["vote_details"] if v["target"] == player_id]
                        f.write(f"    投票者: {', '.join(voters)}\n")
                    
                    if vote_results.get("is_tie"):
                        f.write("\n  ⚖️ 出现平票!\n")
                    f.write(f"\n  🚫 被投出: {vote_results.get('voted_out_name', '未知')}\n")
            
            # 统计信息
            f.write("\n" + "=" * 60 + "\n")
            f.write("📊 游戏统计\n")
            f.write("=" * 60 + "\n")
            f.write(f"• 总死亡数: {self.game_record['game_stats']['total_deaths']}\n")
            f.write(f"• 技能使用次数: {self.game_record['game_stats']['ability_uses']}\n")
            f.write(f"• 投票次数: {len(self.game_record['game_stats']['votes'])}\n")
            
            # 投票有效性统计
            if "vote_validity" in self.metrics:
                total_votes = self.metrics["vote_validity"]["total_votes"]
                valid_votes = self.metrics["vote_validity"]["valid_votes"]
                if total_votes > 0:
                    validity_rate = (valid_votes / total_votes) * 100
                    f.write(f"\n🗳️ 投票统计:\n")
                    f.write(f"  • 总投票数: {total_votes}\n")
                    f.write(f"  • 有效投票数: {valid_votes}\n")
                    f.write(f"  • 投票有效率: {validity_rate:.1f}%\n")
            
            # 评估指标
            f.write("\n" + "=" * 60 + "\n")
            f.write("📈 评估指标\n")
            f.write("=" * 60 + "\n")
            for metric_name, value in self.game_record["final_result"]["metrics"].items():
                if isinstance(value, float):
                    f.write(f"• {metric_name}: {value:.2%}\n")
            
            f.write(f"\n🏆 胜利方: {self.game_record['final_result']['winner']}\n")
            f.write("=" * 60 + "\n")
        
        logging.info(f"📄 分析报告已生成: {report_file}")


def setup_logger(debug: bool = False, log_dir: str = 'logs') -> GameLogger:
    """创建并返回游戏日志记录器
    
    Args:
        debug: 是否开启调试模式
        log_dir: 日志目录
    
    Returns:
        GameLogger: 游戏日志记录器实例
    """
    return GameLogger(debug, log_dir)
