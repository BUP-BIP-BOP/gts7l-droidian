# Droidian — Samsung Galaxy Tab S7 LTE (SM-T875 / `gts7l`)

Порт Droidian (Debian trixie + Phosh поверх Halium) на планшет SM-T875.

Собирается из двух частей: ядро с debian-упаковкой (в форке ядра, CI выдаёт
`linux-bootimage-*.deb`) и пакет адаптации из этого репозитория.

## Статус

Порт **не проверялся на железе**. Он собран переносом с двух рабочих соседей и
дополнен значениями, снятыми с самого T875 в ходе портирования Ubuntu Touch.

| Основание | Что взято |
|---|---|
| [droidian-gts7lwifi](https://github.com/iridite/droidian-gts7lwifi) (SM-T870) | структура порта, конфиги phosh, libinput, pulse, починка маршрутов Wi-Fi |
| [galaxy-tab-s7-plus-droidian](https://github.com/mukahraman/galaxy-tab-s7-plus-droidian) (SM-T970) | полностью рабочий порт того же семейства, источник ядра |
| [gts7l-ubports](https://github.com/BUP-BIP-BOP/gts7l-ubports) | значения загрузчика и конфигурация модема, проверенные на этом устройстве |

T875 отличается от T870 наличием модема — конфигурация ofono добавлена.

## Что уже проверено на этом железе

Эти значения не унаследованы, а сняты со стоковой прошивки T875XXS5DXD1 и
подтверждены загрузкой Ubuntu Touch на том же ядре:

| Параметр | Значение | Замечание |
|---|---|---|
| `RAMDISK_ADDR` | `0x02000000` | **не** дефолт mkbootimg |
| `TAGS_ADDR` | `0x01e00000` | **не** дефолт mkbootimg |
| `OS_VERSION` | `0x16000184` | 11.0.0 / 2024-04, Samsung не поднимала поле |
| `BOARD_NAME` | `SRPTC18C005` | product из стокового boot.img |
| BOOT / RECOVERY | 71303168 / 86888448 | совпало с разметкой байт в байт |
| dtbo | `kona-sec-gts7l-eur-overlay-r00..r07` | ревизия платы устройства — 7 |
| radio HAL | 1.5 | вендор остался на API 30, хотя система Android 13 |

## Сборка

### 1. Ядро

Форкнуть [`mukahraman/kernel_samsung_sm8250`](https://github.com/mukahraman/kernel_samsung_sm8250),
ветка `droidian`, и подложить наши файлы:

```bash
gh repo fork mukahraman/kernel_samsung_sm8250 --clone
cd kernel_samsung_sm8250 && git checkout droidian
cp ../gts7l-droidian/kernel-patches/kernel-info.mk debian/kernel-info.mk
cp ../gts7l-droidian/kernel-patches/extra.config droidian/extra.config
git commit -am "gts7l: SM-T875" && git push
```

CI форка соберёт `linux-bootimage-4.19-*-samsung-gts7l.deb`.

### 2. Пакет адаптации

```bash
cd adaptation && dpkg-buildpackage -us -uc -b
```

### 3. Образ загрузки

```bash
ar x linux-bootimage-*.deb && tar xf data.tar.*
python3 tools/build-bootimg.py boot/boot.img-* boot-gts7l.img
```

Скрипт правит заголовок под ожидания ABL и подписывает образ AVB-футером.
Без этого загрузчик Samsung молча останавливается на заставке.

## Прошивка

Rootfs Droidian берётся с [images.droidian.org](https://images.droidian.org/)
(`droidian-rootfs-api30-arm64`), пишется на userdata, boot и dtbo — heimdall'ом.

**Fastboot на устройстве нет** — только Download Mode и протокол Odin. Под macOS
годится только форк heimdall от amo13: апстрим не делает reset USB перед
рукопожатием и падает с `Failed to send handshake`.

Подробности по прошивке, включая сборку heimdall и работу с разделами, — в
[gts7l-ubports/docs/FLASH.md](https://github.com/BUP-BIP-BOP/gts7l-ubports/blob/master/docs/FLASH.md);
процедура для Droidian отличается только образом rootfs.

## Структура

```
kernel-patches/kernel-info.mk    конфигурация debian-упаковки ядра: модель, dtbo, оффсеты
kernel-patches/extra.config      kconfig-фрагмент Droidian
adaptation/                      пакет adaptation-samsung-gts7l
  etc/phosh/phoc.ini               масштаб панели 2560×1600
  etc/ofono/                       модем: binder-плагин, radio HAL 1.5
  etc/NetworkManager/              маршруты Wi-Fi, swlan0/p2p0 вне управления
  etc/pulse/                       звуковая карта через droid
  etc/libinput/                    калибровка пера и тача
tools/build-bootimg.py           заголовок + AVB-футер под Samsung ABL
tools/make-touchpad-dtbo.py      ориентация тачпада Book Cover
```

## Чего ждать при первом запуске

Пункты, на которых спотыкается это семейство, — из опыта портирования UT:

- **Композитор не стартует.** Samsung'овский `vndservicemanager` отказывает в регистрации сервисов, потому что политика SELinux в контейнере не загружена. Лечится подменой бинарника из порта samsung-q2q.
- **Wi-Fi не поднимается сам.** Нужен `modprobe wlan` и запись в `/dev/wlan` после старта контейнера.
- **Сеть без маршрутов.** NetworkManager получает аренду, но не ставит маршруты — за это отвечает диспетчер в пакете адаптации.
- **Смена образа.** При замене rootfs стирать состояние на userdata, иначе конфигурация от прошлой версии ломает сессию.

## Лицензия

GPL-3.0. Файлы, перенесённые из портов T870 и T970, принадлежат их авторам.
