# dependency_viz.py - исправленная версия

import argparse
import sys
import requests
import subprocess
from graphviz import Digraph
import os

class DependencyVisualizer:
    def __init__(self):
        self.args = None
        self.deps = {}
        self.all_deps_graph = {}
        self.visited = set()
        self.version_cache = {}  # Кэш версий

    def parse_arguments(self):
        parser = argparse.ArgumentParser(
            description="Rust Cargo Dependency Visualizer",
            epilog="Пример: python3 %(prog)s --package serde --repo https://crates.io/crates/serde"
        )
        parser.add_argument("--package", required=True, help="Имя пакета")
        parser.add_argument("--repo", required=True, help="URL репозитория")
        parser.add_argument("--test-mode", action="store_true", help="Тестовый режим")
        parser.add_argument("--version", default="latest", help="Версия пакета")
        parser.add_argument("--filter", default="", help="Фильтр пакетов")
        self.args = parser.parse_args()
        self.print_config()

    def print_config(self):
        print("=" * 50)
        print("КОНФИГУРАЦИЯ")
        print("=" * 50)
        for key, value in vars(self.args).items():
            print(f"{key:12} = {value}")
        print("=" * 50 + "\n")

    def get_latest_version(self, package):
        """Получает последнюю версию пакета"""
        if package in self.version_cache:
            return self.version_cache[package]
        
        try:
            url = f"https://crates.io/api/v1/crates/{package}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                latest = data['crate']['newest_version']
                self.version_cache[package] = latest
                print(f"[INFO] Последняя версия '{package}': {latest}")
                return latest
            else:
                print(f"[ERROR] Не удалось получить версию для '{package}': {response.status_code}")
                return None
        except Exception as e:
            print(f"[ERROR] Ошибка при получении версии '{package}': {e}")
            return None

    def fetch_dependencies_for_package(self, package, version=None):
        """Получает зависимости для конкретного пакета и версии"""
        if self.args.filter and self.args.filter in package:
            return []
        
        # Определяем версию
        if version is None or version == "latest":
            actual_version = self.get_latest_version(package)
            if actual_version is None:
                return []
        else:
            actual_version = version
        
        if not actual_version:
            return []
        
        url = f"https://crates.io/api/v1/crates/{package}/{actual_version}/dependencies"
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                dependencies = []
                for dep in data.get('dependencies', []):
                    dep_name = dep['crate_id']
                    if self.args.filter and self.args.filter in dep_name:
                        continue
                    dependencies.append(dep_name)
                return dependencies
            elif response.status_code == 404:
                # Пробуем найти любую доступную версию
                print(f"[WARNING] Версия {actual_version} не найдена для '{package}'")
                latest = self.get_latest_version(package)
                if latest and latest != actual_version:
                    print(f"[INFO] Пробуем версию {latest}")
                    return self.fetch_dependencies_for_package(package, latest)
                return []
            else:
                print(f"[ERROR] Ошибка для '{package}': {response.status_code}")
                return []
        except Exception as e:
            print(f"[ERROR] Сетевая ошибка для '{package}': {e}")
            return []

    def build_dependency_graph(self):
        """Строит граф зависимостей (упрощенный, depth=1)"""
        print(f"[INFO] Получение зависимостей для '{self.args.package}'...")
        
        # Получаем прямые зависимости
        direct_deps = self.fetch_dependencies_for_package(self.args.package, self.args.version)
        
        if not direct_deps:
            print(f"[INFO] Зависимости не найдены для '{self.args.package}'")
            self.deps = {self.args.package: []}
            self.all_deps_graph = {self.args.package: []}
            return
        
        self.deps = {self.args.package: direct_deps}
        self.all_deps_graph = {self.args.package: direct_deps}
        
        for dep in direct_deps[:3]:  # Ограничим для скорости
             if dep not in self.visited:
                 self.visited.add(dep)
                 sub_deps = self.fetch_dependencies_for_package(dep, "latest")
                 if sub_deps:
                     self.all_deps_graph[dep] = sub_deps
        
        print(f"[INFO] Найдено зависимостей: {len(direct_deps)}")

    def fetch_dependencies(self):
        """Основной метод получения данных"""
        if self.args.test_mode:
            print("[TEST MODE] Используются тестовые данные")
            self.deps = {
                "serde": ["serde_derive", "serde_core"],
                "tokio": ["futures", "mio", "tokio-macros"],
                "reqwest": ["hyper", "tokio", "serde"]
            }
            self.all_deps_graph = self.deps
        else:
            self.build_dependency_graph()
        
        # Вывод прямых зависимостей (Этап 2)
        if self.args.package in self.deps:
            print("\n" + "=" * 50)
            print("ПРЯМЫЕ ЗАВИСИМОСТИ")
            print("=" * 50)
            for dep in self.deps[self.args.package]:
                print(f"  → {dep}")
            print("=" * 50)
        else:
            print(f"[INFO] Прямые зависимости не найдены")

    def generate_graphviz(self):
        """Генерация Graphviz с проверкой установки"""
        try:
            # Проверяем доступность dot
            result = subprocess.run(['which', 'dot'], capture_output=True, text=True)
            if result.returncode != 0:
                print("\n" + "=" * 60)
                print("ВНИМАНИЕ: Graphviz не установлен!")
                print("=" * 60)
                print("Установите Graphviz командой:")
                print("  Ubuntu/Debian: sudo apt install graphviz")
                print("  Fedora: sudo dnf install graphviz")
                print("  macOS: brew install graphviz")
                print("\nАльтернатива: будет создан только DOT-файл")
                print("=" * 60)
                
                # Создаем DOT-файл без рендеринга
                self.create_dot_file_only()
                return
        except:
            pass
        
        # Если dot доступен, создаем полную визуализацию
        if not self.all_deps_graph:
            print("[ERROR] Нет данных для визуализации")
            return
        
        dot = Digraph(comment=f"Dependencies of {self.args.package}")
        
        # Главный пакет
        dot.node(self.args.package, self.args.package, shape='box', color='blue')
        
        # Зависимости
        for package, deps in self.all_deps_graph.items():
            if package != self.args.package:
                dot.node(package, package)
            
            for dep in deps:
                dot.edge(package, dep)
        
        # Выводим DOT код
        print("\n" + "=" * 60)
        print("GRAPHVIZ DOT КОД")
        print("=" * 60)
        print(dot.source)
        print("=" * 60)
        
        # Сохраняем
        try:
            filename = f"{self.args.package}_deps"
            output_path = dot.render(filename, cleanup=False, format='png')
            print(f"\n[SUCCESS] Граф сохранён: {output_path}")
            
            # Также сохраняем DOT файл отдельно
            with open(f"{self.args.package}_deps.dot", "w") as f:
                f.write(dot.source)
            print(f"[INFO] DOT файл сохранён: {self.args.package}_deps.dot")
        except Exception as e:
            print(f"[ERROR] Не удалось создать изображение: {e}")
            print("[INFO] Сохраняю только DOT файл...")
            with open(f"{self.args.package}_deps.dot", "w") as f:
                f.write(dot.source)

    def create_dot_file_only(self):
        """Создает только DOT файл без рендеринга"""
        if not self.all_deps_graph:
            return
        
        dot_content = f"digraph {{\n  rankdir=LR;\n  node [shape=box];\n\n"
        dot_content += f'  "{self.args.package}" [color=blue];\n\n'
        
        # Добавляем все узлы и связи
        for package, deps in self.all_deps_graph.items():
            for dep in deps:
                dot_content += f'  "{package}" -> "{dep}";\n'
        
        dot_content += "}\n"
        
        # Сохраняем DOT файл
        filename = f"{self.args.package}_deps.dot"
        with open(filename, "w") as f:
            f.write(dot_content)
        
        print(f"\n[INFO] DOT файл создан: {filename}")
        print("\nДля визуализации выполните:")
        print(f"  dot -Tpng {filename} -o {self.args.package}_deps.png")
        print("\nИли установите Graphviz (см. инструкцию выше)")

    def run_three_examples(self):
        """Запуск для 3 пакетов"""
        examples = [
            {"package": "serde", "version": "latest"},
            {"package": "tokio", "version": "1.0"},
            {"package": "clap", "version": "4.0"},
        ]
        
        print("\n" + "=" * 60)
        print("АНАЛИЗ 3 ПАКЕТОВ")
        print("=" * 60)
        
        original_package = self.args.package
        
        for i, example in enumerate(examples, 1):
            print(f"\n{'='*40}")
            print(f"ПАКЕТ {i}/{len(examples)}: {example['package']}")
            print(f"{'='*40}")
            
            self.args.package = example['package']
            self.args.version = example['version']
            
            # Сбрасываем состояние
            self.deps = {}
            self.all_deps_graph = {}
            self.visited = set()
            self.version_cache = {}
            
            # Получаем зависимости
            print(f"[INFO] Анализ {example['package']}...")
            self.build_dependency_graph()
            
            # Создаем DOT файл
            self.create_dot_file_only()
        
        # Восстанавливаем
        self.args.package = original_package
        print(f"\n[SUCCESS] Анализ 3 пакетов завершен!")
        print("DOT файлы созданы в текущей директории")

    def run(self):
        """Основной запуск"""
        try:
            self.parse_arguments()
            self.fetch_dependencies()
            
            # Предлагаем анализ 3 пакетов
            if not self.args.test_mode:
                print("\n" + "=" * 60)
                print("ВЫБОР РЕЖИМА")
                print("=" * 60)
                choice = input("1. Только текущий пакет\n2. Текущий + 3 примера\nВыбор (1/2): ")
                
                if choice == "2":
                    self.run_three_examples()
                    return
            
            self.generate_graphviz()
            
            print("\n" + "=" * 60)
            print("ВЫПОЛНЕНО")
            print("=" * 60)
            print("✓ Этап 1: CLI конфигурация")
            print("✓ Этап 2: Сбор данных")
            print("✓ Этап 5: Визуализация")
            
        except KeyboardInterrupt:
            print("\n\n[INFO] Прервано пользователем")
        except Exception as e:
            print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    viz = DependencyVisualizer()
    viz.run()