# Отчёт по домашнему заданию №3: модель из реестра в кластере, DVC, Self-Hosted Runner и HPA

---

## 1. Таблица подтверждений

| Пункт задания | Доказательство (ссылка / файл) | Комментарий |
| :--- | :--- | :--- |
| **1. Платформа (Traefik, MLflow)** | `docs/screenshots/01_mlflow_ingress.png` | `http://mlflow.localhost` открывается в режиме Model training через Ingress на 80 порту |
| **Вывод подов и ингрессов** | См. Раздел 1.1 ниже | `kubectl get pods,ingress -A` - все поды 1/1 Running |
| **2. Реестр и гейт** | `docs/screenshots/02_model_registry_aliases.png` | Модель `toxic-comment-clf`, видны версии, колонка Aliases с `@champion` и `@challenger` |
| **Решение гейта** | См. Раздел 1.2 ниже | 3 последовательных прогона: v1 -> champion, v2 -> отклонен, v3 -> champion |
| **3. Сервис по алиасу и откат** | См. Раздел 1.3 ниже | Замер времени отката: **26 секунд** без пересборки контейнера |
| **4. Self-hosted runner (CI/CD)** | `https://github.com/volkovaia/mlops_1/actions/runs/37019578385` | В логе джобы `deploy` виден `Runner name: 'local-kind-runner'` |
| **Статус раннера в GitHub** | `docs/screenshots/03_github_runner_idle.png` | Страница Settings -> Actions -> Runners со статусом `Idle` |
| **5. Версии данных в DVC** | Файл `data/train.csv.dvc` в git | Вывод `dvc push` (1 file pushed) и `dvc diff HEAD` (1 modified) |
| **6. Автомасштабирование HPA** | `docs/screenshots/04_hpa_scaling.png` | Масштабирование реплик `2 -> 4 -> 6 -> 2` под нагрузкой Locust |
| **События HPA** | См. Раздел 1.4 ниже | Вывод `kubectl describe hpa` со строками `SuccessfulRescale` |
| **Поломка 1 (Алиас): красный** | `https://github.com/volkovaia/mlops_1/actions/runs/37023332012` | Алиас `prod` не найден в реестре (код 503 на `/ready`) |
| **Поломка 1 (Алиас): зелёный** | `https://github.com/volkovaia/mlops_1/actions/runs/37023499455` | Возвращён алиас `champion` |
| **Поломка 2 (Кластер): красный** | `https://github.com/volkovaia/mlops_1/actions/runs/37023868566` | Неверный `KIND_CLUSTER: wrong-cluster` (контекст не найден) |
| **Поломка 2 (Кластер): зелёный** | `https://github.com/volkovaia/mlops_1/actions/runs/37024200502` | Контекст возвращён на `kind-mlpro-cluster` |
| **Поломка 3 (Ingress): красный** | `https://github.com/volkovaia/mlops_1/actions/runs/37024452114` | Опечатка в хосте `toxic-wrong.localhost` (404 на smoke-тесте) |
| **Поломка 3 (Ingress): зелёный** | `https://github.com/volkovaia/mlops_1/actions/runs/37024560938` | Хост возвращён на `toxic.localhost` |

---

### 1.1. Вывод `kubectl get pods,ingress -A`
```text
NAMESPACE            NAME                                                      READY   STATUS    RESTARTS   AGE
default              pod/postgres-db59c7c89-tmcwj                              1/1     Running   0          8h
default              pod/toxic-service-66d7fb4d79-27885                        1/1     Running   0          15m
default              pod/toxic-service-66d7fb4d79-z7wq4                        1/1     Running   0          15m
kube-system          pod/coredns-7db6d8ff4d-q6snf                              1/1     Running   0          10h
kube-system          pod/coredns-7db6d8ff4d-zcpgf                              1/1     Running   0          10h
kube-system          pod/etcd-mlpro-cluster-control-plane                      1/1     Running   0          10h
kube-system          pod/kindnet-t5d88                                         1/1     Running   0          10h
kube-system          pod/kube-apiserver-mlpro-cluster-control-plane            1/1     Running   0          10h
kube-system          pod/kube-controller-manager-mlpro-cluster-control-plane   1/1     Running   0          10h
kube-system          pod/kube-proxy-5fqsp                                      1/1     Running   0          10h
kube-system          pod/kube-scheduler-mlpro-cluster-control-plane            1/1     Running   0          10h
kube-system          pod/metrics-server-54d9b4b96-v4l2z                        1/1     Running   0          45m
local-path-storage   pod/local-path-provisioner-65749bdd48-p6rlg               1/1     Running   0          10h
mlflow               pod/mlflow-6f855576d8-lsflz                               1/1     Running   0          10h
traefik              pod/traefik-7dcfb75d68-8x49l                              1/1     Running   0          9h

NAMESPACE   NAME                                             CLASS     HOSTS              ADDRESS   PORTS   AGE
default     ingress.networking.k8s.io/toxic-service-ingress  traefik   toxic.localhost              80      2h
mlflow      ingress.networking.k8s.io/mlflow-ingress         traefik   mlflow.localhost             80      9h
```
### 1.2. Решения валидационного гейта (3 запуска подряд)
```text
Запуск 1 (C=1.0)
No current champion found. Promoting first model to champion!
-> Assigned alias 'challenger' to version 1
-> Assigned alias 'champion' to version 1

Запуск 2 (C=0.001, намеренное ухудшение)
-> Assigned alias 'challenger' to version 2
Current champion (v1) pr_auc: 0.9942
Comparison: New 0.9514 vs Champion 0.9942 (Delta: -0.0427, Required: +0.0001)
-> GATE REJECTED. Version 2 remains only 'challenger'.

Запуск 3 (C=20.0, улучшение)
-> Assigned alias 'challenger' to version 3
Current champion (v1) pr_auc: 0.9942
Comparison: New 0.9945 vs Champion 0.9942 (Delta: +0.0003, Required: +0.0001)
-> GATE PASSED! Version 3 promoted to 'champion'!
```
### 1.3. Решения валидационного гейта (3 запуска подряд)
Ответ /health ДО отката (модель @champion указывала на v3):
```json
{"status":"ok","model_version":"v3","model_name":"toxic-comment-clf"}
```
В UI MLflow алиас champion перевешен на Version 1. 
Выполнен kubectl rollout restart deployment/toxic-service и kubectl rollout status. 
Ответ /health после отката (модель переключилась на v1 без пересборки Docker-образа): 
```json
{"status":"ok","model_version":"v1","model_name":"toxic-comment-clf"}
```
Время отката: ровно 26 секунд.

### 1.4. События автомасштабирования HPA (kubectl describe hpa)
```text
Events:
  Type    Reason             Age    From                       Message
  ----    ------             ----   ----                       -------
  Normal  SuccessfulRescale  10m    horizontal-pod-autoscaler  New size: 4; reason: cpu resource utilization (percentage of request) above target
  Normal  SuccessfulRescale  9m45s  horizontal-pod-autoscaler  New size: 6; reason: cpu resource utilization (percentage of request) above target
  Normal  SuccessfulRescale  2m15s  horizontal-pod-autoscaler  New size: 2; reason: All metrics below target
```

## 2. Разбор трёх красных прогонов

### Поломка 1: Модели нет в реестре (`MODEL_ALIAS: prod`)

- **Красная job:** `deploy`.
- **Шаг падения:** Wait for deployment rollout (таймаут).
- **Статус пода:** `CrashLoopBackOff`
- В логах контейнера зафиксировано: `Failed to load model from MLflow: RESOURCE_DOES_NOT_EXIST: Registered Model with name=toxic-comment-clf and alias=prod not found`. Эндпоинт `/ready` возвращает код 503, проверка `startupProbe` не проходит, поды не становятся Ready.
- **Как понять причину без diff:** по коду 503 на `/ready` и сообщению `RESOURCE_DOES_NOT_EXIST` в логах пода сразу видно, что запрашиваемый алиас отсутствует в Model Registry.

### Поломка 2: Runner не видит кластер (`KIND_CLUSTER: wrong-cluster`)

- **Красная job:** `deploy`.
- **Шаг падения:** Deploy Postgres in cluster.
- **Статус пода:** Поды не созданы.
- `error: no context exists with the name: "kind-wrong-cluster"`.
- **Как понять причину без diff:** ошибка выводится в CLI на команде `kubectl`, указывая на отсутствие запрошенного контекста в конфигурации kubeconfig раннера.

### Поломка 3: Ingress мимо (несовпадение хоста со smoke-тестом)

- **Красная job:** `deploy`.
- **Шаг падения:** Run Smoke Test via Ingress.
- **Статус пода:** Running (1/1 Ready), все поды здоровы
- Команда smoke-теста падает с ошибкой `curl: (22) The requested URL returned error: 404 Not Found` или `JSONDecodeError` от пустой строки.
- **Как понять причину без diff:** поды здоровы и отдают 200 на локальных портах, но `curl` через контроллер Ingress возвращает 404. Это  свидетельствует о расхождении заголовка Host в запросе и секции `rules.host` в манифесте `k8s/ingress.yaml`.

## 3. Ответы на восемь вопросов

### 1. Почему `tests` и `build` по-прежнему идут в облаке GitHub, а `deploy` не может? Какие ещё есть способы доставить код в кластер за NAT и почему мы выбрали runner?

Джобы `tests` и `build` изолированы: для прогона unit-тестов и сборки Docker-образа с последующим пушем в GHCR нужен стандартный Linux-раннер и доступ в интернет. Локальный кластер kind развёрнут на рабочей машине за домашним NAT и не имеет публичного IP-адреса, поэтому облачные раннеры GitHub не могут направить команды `kubectl` напрямую на порт 6443.

Альтернативные способы доставки:

- Настройка VPN-туннеля между облачным раннером и локальной сетью
- Использование сервисов проброса туннелей (ngrok, Cloudflare Tunnels)
- GitOps-подход, когда агент внутри кластера сам опрашивает Git-репозиторий и применяет манифесты 

Я выбрала self-hosted runner, так как он устанавливается в один Docker-контейнер, работает по исходящему безопасному соединению с GitHub, не требует открытия белых IP-адресов и настройки туннелей.

### 2. Зачем runner запущен с `--network kind`, сокетом Docker и `--group-add 0`? Что сломается без каждого из трёх?

- `--network kind`: помещает контейнер раннера в ту же Docker-сеть, где живут ноды кластера kind. Без этого раннер не сможет подключиться к `https://mlpro-cluster-control-plane:6443` и хосту Ingress Traefik.
- `-v /var/run/docker.sock:/var/run/docker.sock`: пробрасывает UNIX-сокет хостового Docker-демона внутрь раннера, позволяя выполнять команды `docker`. Без сокета контейнер раннера не сможет обращаться к Docker-движку хоста.
- `--group-add 0`: добавляет пользователя внутри контейнера в группу root (GID 0), которой принадлежит смонтированный сокет Docker на хосте. Без этого раннер получит ошибку `permission denied` при попытке доступа к сокету `/var/run/docker.sock`.

### 3. Почему `create secret` заменили на `--dry-run=client -o yaml | kubectl apply`? Что будет при втором деплое без этой замены?

Команда `kubectl create secret` предназначена для первичного создания ресурса. При повторном деплое она завершится с ошибкой `Error from server (AlreadyExists): secrets "toxic-secret" already exists`, пайплайн упадёт.

Связка `--dry-run=client -o yaml | kubectl apply -f -` генерирует манифест секрета на лету в памяти клиента и передаёт его `kubectl apply`, которая либо создаёт секрет (если его нет), либо обновляет его без сбоев.

### 4. Чем `challenger` отличается от `champion`? Почему сервис просит алиас, а не номер версии? Сравните откат модели через алиас с откатом кода через `rollout undo`.

`champion` - это текущая проверенная рабочая версия модели, показавшая лучший результат. `challenger` - версия-кандидат, которая прошла обучение, но ещё не превзошла по метрикам champion.

Сервис запрашивает алиас, чтобы абстрагироваться от монотонно растущих номеров версий (v1, v12, v45). При выходе новой лучшей модели или при откате адрес запроса остаётся неизменным.

Откат модели по алиасу: меняет указатель в базе данных реестра MLflow. При перезапуске под подтягивает старую модель без пересборки Docker-образа, перекомпиляции зависимостей и без правок манифестов Kubernetes (занимает секунды).

Откат кода (`rollout undo`): откатывает ревизию самого Deployment в Kubernetes на предыдущий Docker-образ. Это тяжелее, так как требует перезагрузки контейнера с потенциально другим кодом приложения и зависимостями.

### 5. Что будет, если задеплоить сервис в кластер, где никто ещё не обучил модель? Как это увидеть в k9s и в логе CI?

При старте сервис попытается запросить модель из реестра MLflow, получит ошибку `RESOURCE_DOES_NOT_EXIST`, выставит переменную пайплайна в `None` и начнёт отдавать код 503 Service Unavailable на эндпоинте `/ready`.

В k9s: поды сервиса сначала будут иметь статус `Running (0/1)`, а через 20 секунд (10 неудач `startupProbe`) перейдут в `CrashLoopBackOff` с красной подсветкой и растущим числом рестартов.

В логе CI: шаг Wait for deployment rollout упадёт по таймауту (`timed out waiting for the condition`), а в шаге диагностики `describe pods` будет зафиксировано `Startup probe failed: HTTP probe failed with statuscode: 503`.

### 6. Проследите запрос от браузера до пода MLflow: какие порты и какие компоненты он проходит? Зачем MLflow нужны `--allowed-hosts` и `--cors-allowed-origins`, и почему порт 80 задаётся при создании кластера, а не потом?

Путь запроса: браузер (`http://mlflow.localhost:80`) -> сетевой интерфейс хоста (порт 80) -> Docker container port mapping (порт 80 контейнера `mlpro-cluster-control-plane`) -> Ingress-контроллер Traefik (порт 80, точка входа `web`) -> Kubernetes Service `mlflow` (порт 5000) -> Pod `mlflow` (Uvicorn на порту 5000 внутри контейнера).

`--allowed-hosts` и `--cors-allowed-origins`: флаги разрешают обработку HTTP-заголовков Host, отличных от стандартного `localhost`, предотвращая отказ с кодом 403.

Порт 80 задаётся при создании кластера: kind создаёт узлы кластера как обычные Docker-контейнеры. В архитектуре Docker проброс портов (`-p 80:80`) фиксируется на этапе создания контейнера-ноды и не может быть динамически добавлен в работающий контейнер стандартными средствами без его пересоздания.

### 7. Посчитайте по формуле из лекции, сколько реплик HPA должен был выставить при вашей загрузке CPU, и сравните с тем, что он выставил. Почему вниз реплики уходили дольше, чем вверх?

Формула HPA:

```text
DesiredReplicas = ceil(CurrentReplicas * (CurrentMetricValue / TargetMetricValue))
```
**Расчёт:** При базовых 2 репликах под нагрузкой загрузка CPU поднялась до 174% (целевое значение: 60%):

```text
DesiredReplicas = ceil(2 * (174 / 60)) = ceil(2 * 2.9) = ceil(5.8) = 6
```

**Сравнение:** HPA выставил 6 реплик (достигнув заданного `maxReplicas: 6`), что совпадает с теоретическим расчётом по формуле.

**Почему вниз дольше:** в Kubernetes HPA по умолчанию действует окно стабилизации масштабирования вниз. Это сделано намеренно для защиты от эффекта дребезга, чтобы кратковременные провалы в трафике не приводили к уничтожению подов, за которым последовал бы повторный всплеск нагрузки.

### 8. Что лежит в git, а что в хранилище DVC? По шагам: как восстановить ровно те данные, на которых обучена версия N вашей модели в реестре?

В Git лежат: исходный код, пайплайн, манифесты и указатели DVC: файл `data/train.csv.dvc` (содержит md5-хэш данных и размер) и служебные файлы `.dvc/config`, `.dvcignore`.

В хранилище DVC (remote): лежат реальные тяжелые файлы данных, названные по их хэш-суммам (в каталоге `../dvc-storage`).

Как восстановить данные версии N:

1. Зайти в MLflow Model Registry, открыть версию N и найти параметр прогона `data_md5`.
2. Найти коммит в Git, в котором файл `data/train.csv.dvc` содержал именно этот хэш (через `git log -S <хэш> data/train.csv.dvc`).
3. Переключиться на этот коммит: `git checkout <commit_sha> -- data/train.csv.dvc`.
4. Запустить `uv run dvc checkout` — DVC мгновенно извлечёт из хранилища и восстановит в рабочую директорию точную копию CSV-файла, на которой обучалась модель.

## 4. Журнал проблем

### Кодировка UTF-16 LE при создании `kind-config.yaml`

- `kind create cluster` падал с ошибкой `unknown apiVersion:`
- **Причина:** Windows PowerShell сохранял файл в кодировке UTF-16 LE с BOM.
-  Файл пересохранён в чистом UTF-8 без BOM через `[System.IO.File]::WriteAllText`

### Ошибка 403 Forbidden от MLflow

- Сервис `toxic-service` отдавал 503 на `/ready`, в логах было `403 != 200: Invalid Host header - possible DNS rebinding attack detected`
- **Причина:** MLflow блокировал сетевые запросы от сервиса по внутреннему DNS-имени Kubernetes (`mlflow.mlflow.svc.cluster.local`)
- В аргументы запуска MLflow добавлен флаг `--allowed-hosts=*`

### Отсутствие артефактов модели на сервере (`No such artifact: 'MLmodel'`)

- Сервис не мог скачать модель из реестра, директория `/mlflow/artifacts` внутри пода была пустой
- **Причина:** эксперимент был создан со схемой `file:///`, поэтому клиент на Windows сохранял файлы локально, не отправляя их на сервер
- В манифест MLflow добавлены флаги `--serve-artifacts` и `--default-artifact-root=mlflow-artifacts:/`, а в `train.py` задано явное создание эксперимента со схемой `mlflow-artifacts:/`

### Ошибка регистрации Self-Hosted Runner (401 Unauthorized)

- Контейнер раннера падал с ошибкой `curl: (22) The requested URL returned error: 401`
- **Причина:** в переменной `ACCESS_TOKEN` передавался одноразовый registration token вместо классического 
- Создан GitHub Personal Access Token с правами `repo` и передан в контейнер через `ACCESS_TOKEN`

### Отсутствие бинарника kubectl внутри раннера

- При запуске деплоя раннер выдавал `executable file not found in $PATH: kubectl`
- Бинарник `kubectl` v1.30.2 скачан и установлен в директорию `/usr/local/bin` внутри контейнера раннера

### Ошибка парсинга IPv6-адреса в smoke-тесте

- Шаг smoke-теста падал с ошибкой `JSONDecodeError: Expecting value: line 1 column 1`
- **Причина:** команда `getent hosts` возвращала IPv6-адрес `fc00:...`, который `curl` не мог обработать без квадратных скобок в URL
- Запросы `curl` переведены на прямое имя контейнера `http://mlpro-cluster-control-plane/` с заголовком `Host: toxic.localhost`