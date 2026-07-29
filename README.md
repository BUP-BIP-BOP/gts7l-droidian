# Droidian — Samsung Galaxy Tab S7 LTE (SM-T875 / `gts7l`)

Порт Droidian (Debian trixie + Phosh поверх Halium) на планшет SM-T875.

Собирается из двух частей: ядро с debian-упаковкой (в форке ядра, CI выдаёт
`linux-bootimage-*.deb`) и пакет адаптации из этого репозитория.

## Статус

Порт **загружается на железе**: Phosh стартует, работают тач, автоповорот,
камеры и Wi-Fi. Заставка Droidian при загрузке не показывается — экран остаётся
на логотипе Samsung до появления оболочки.

Основа собрана переносом с двух рабочих соседей и дополнена значениями, снятыми
с самого T875 в ходе портирования Ubuntu Touch.

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

> **Известная поломка сборки.** Сниппет упаковки Droidian собирает
> `init_boot.img` безусловно, с `--header_version 2` и без `--dtb`. Свежий
> `mkbootimg` такую комбинацию отвергает:
>
> ```
> ValueError: DTB image must not be empty.
> ```
>
> и падает вся сборка. Устройство не GKI, `init_boot` в пакет не попадает, так
> что цель заглушена в `debian/rules` форка. Убрать заглушку, когда сниппет
> перестанет собирать `init_boot` безусловно.

### 2. Пакет адаптации

```bash
cd adaptation && dpkg-buildpackage -us -uc -b
```

### 3. Комплект для прошивки

```bash
./tools/make-flashable.sh          # заберёт .deb из CI форка ядра
./tools/make-flashable.sh path.deb # или из локального пакета
```

Скрипт распакует пакет, соберёт `boot.img` и `boot-rescue.img` под ожидания
Samsung ABL, пропатчит `dtbo.img` под тачпад Book Cover и положит рядом
`vbmeta-disabled.img`. Всё в `out/`.

Правка заголовка и AVB-футер обязательны: без них загрузчик молча
останавливается на заставке, не передавая управление ядру.

Скрипт также **переупорядочивает секцию dtb** по ревизии SoC (kona v1, v2,
v2.1). Сниппет упаковки склеивает device tree в порядке glob'а, где первым
идёт v2.1; загрузчик Samsung на kona отдаёт ядру блоб по позиции, а не по
`qcom,msm-id`, и ядро получает device tree от чужой ревизии. Оно падает раньше
инициализации консоли — pstore пуст, планшет стоит на заставке и не
перезагружается. Симптом неотличим от неверных оффсетов.

Инструменты на macOS: `avbtool` пакетом не ставится — `tools/get-avbtool.sh`
подтянет его из AOSP. Оба скрипта принимают пути через переменные:

```bash
export AVBTOOL=$(./tools/get-avbtool.sh)
brew install dtc          # нужен только для патча тачпада
export DTC=$(which dtc)
```

Без `dtc` патч dtbo пропускается, и `make-flashable.sh` кладёт стоковый dtbo —
на загрузку это не влияет, отличается только ориентация тачпада Book Cover.

## Прошивка

Rootfs Droidian берётся с [images.droidian.org](https://images.droidian.org/)
(`droidian-rootfs-api30-arm64`), пишется на userdata, boot и dtbo — heimdall'ом.

**Fastboot на устройстве нет** — только Download Mode и протокол Odin. Под macOS
годится только форк heimdall от amo13: апстрим не делает reset USB перед
рукопожатием и падает с `Failed to send handshake`.

### Обязательный шаг: расширить rootfs

```bash
./tools/grow-rootfs.sh 16G      # планшет в TWRP
```

Образ с images.droidian.org приезжает заполненным на 100% — свободно около 16 МБ.
Ветка LVM на этом устройстве не срабатывает: userdata отформатирован в ext4,
тома `droidian` нет (`Volume group "droidian" not found`), initramfs откатывается
на файл `/data/rootfs.img` и **не растит** его. Система при этом грузится, но
без места не поднимается ни контейнер, ни оболочка:

```
systemd-journald[829]: Failed to open system journal: No space left on device
init: SetupMountNamespaces failed: No space left on device
```

Внешне это выглядит как зависание на логотипе Samsung — ровно как отказ
загрузчика, хотя ядро и systemd уже работают. Отличить можно по `pstore`: если
в `console-ramoops-0` есть `Run /init` и строки systemd — ядро стартовало, дело
в пользовательском пространстве.

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
tools/grow-rootfs.sh              расширение /data/rootfs.img из TWRP
```

## Чего ждать при первом запуске

Пункты, на которых спотыкается это семейство, — из опыта портирования UT:

- **Композитор не стартует.** Samsung'овский `vndservicemanager` отказывает в регистрации сервисов, потому что политика SELinux в контейнере не загружена. Лечится подменой бинарника из порта samsung-q2q.
- **Wi-Fi не поднимается сам.** Нужен `modprobe wlan` и запись в `/dev/wlan` после старта контейнера.
- **Сеть без маршрутов.** NetworkManager получает аренду, но не ставит маршруты — за это отвечает диспетчер в пакете адаптации.
- **Смена образа.** При замене rootfs стирать состояние на userdata, иначе конфигурация от прошлой версии ломает сессию.

## Лицензия

GPL-3.0. Файлы, перенесённые из портов T870 и T970, принадлежат их авторам.
