## [1.4.1](https://github.com/m3rrym4n/smoke-shack/compare/v1.4.0...v1.4.1) (2026-11-07)


### Bug Fixes

* draw target line for each probe ([dfe52cc](https://github.com/m3rrym4n/smoke-shack/commit/dfe52ccb87533d4f5fc479453cc02e06f63b64a5))
* preserve ingress path for grill images ([51757a1](https://github.com/m3rrym4n/smoke-shack/commit/51757a1954ca9598ae128f7047c1517befa40023))

# [1.4.0](https://github.com/m3rrym4n/smoke-shack/compare/v1.3.5...v1.4.0) (2026-11-07)


### Bug Fixes

* align grill profile with Home Assistant entities ([653f665](https://github.com/m3rrym4n/smoke-shack/commit/653f665814f1f22a3fa1c5e0364ca5f5fbaad40a))
* backfill connected grill status entities ([9624c67](https://github.com/m3rrym4n/smoke-shack/commit/9624c67afd7f4e3968e31bdce591f3f93f4f73ca))
* cache discovered grill identities ([604b9e3](https://github.com/m3rrym4n/smoke-shack/commit/604b9e3b3427902063c513f3865c3df4daa8fc7c))
* chain grill pictures migration after fuel ([fdd45ef](https://github.com/m3rrym4n/smoke-shack/commit/fdd45ef40a8d56b98552a97180575e35fdd668a0))
* derive restarted probe state from values ([33cfe69](https://github.com/m3rrym4n/smoke-shack/commit/33cfe696787279db3c1db7a018cbb5fca4fcdac8))
* detect logo image type before SVG content ([345c23a](https://github.com/m3rrym4n/smoke-shack/commit/345c23a8faf1371ac3b67c358df6c4e23ca2591f))
* group fuel pantry items by type ([f94cfcb](https://github.com/m3rrym4n/smoke-shack/commit/f94cfcb065ae449e3a27e6b798aedc8a79b9538d))
* make dropdown option lists readable ([5aac5de](https://github.com/m3rrym4n/smoke-shack/commit/5aac5ded1b4a32f39bfb0ac8484c037c1c74728c))
* make fuel price per pound optional ([80dce53](https://github.com/m3rrym4n/smoke-shack/commit/80dce5362311f5b46a91e1bffa8599703ce756d3))
* preserve fresh snapshot across telemetry outages ([afc5724](https://github.com/m3rrym4n/smoke-shack/commit/afc57245477a6b88cf11a682d77fcfbe89089546))
* preserve fuel photo folders on restore ([976fc6c](https://github.com/m3rrym4n/smoke-shack/commit/976fc6c404bbcc14b9dff74e303a329e88c00475))
* recognize migrated entities yaml grill ([5fb91b8](https://github.com/m3rrym4n/smoke-shack/commit/5fb91b8b936b764196636b03261516b5306452ed))
* replace grill maker dial placeholder ([6d21e51](https://github.com/m3rrym4n/smoke-shack/commit/6d21e51c4195cb3ae3bc653d5a0bb13a7aeae1a4))
* show discovered grill names everywhere ([02e32bc](https://github.com/m3rrym4n/smoke-shack/commit/02e32bca08dc08b29f091d559288050ccab5940a))


### Features

* add equipment and channels schema ([2b7e3fa](https://github.com/m3rrym4n/smoke-shack/commit/2b7e3faed99bfa3d526f907c11f85963c86b3fa3))
* add grill settings page ([8b3a5f7](https://github.com/m3rrym4n/smoke-shack/commit/8b3a5f7f9da2ddfc2b4d9980b2054286494b3a0a))
* add Masterbuilt Gravity 800 mapping profile ([68adb5a](https://github.com/m3rrym4n/smoke-shack/commit/68adb5a8b082b6c24233e7c99f68e3f9b1d5a9f3))
* add typed fuel pantry and cook picker ([81f3c0d](https://github.com/m3rrym4n/smoke-shack/commit/81f3c0dae66591999bce4cc9f320e57c870d680a))
* choose grill for historical cooks ([41ae17f](https://github.com/m3rrym4n/smoke-shack/commit/41ae17f3507203e5eb84ff6192736e82497bc634))
* connect one grill at a time ([2db3366](https://github.com/m3rrym4n/smoke-shack/commit/2db33661a86df50592d01a189be29fe8964f7582))
* convert legacy samples to channel readings ([b9c0113](https://github.com/m3rrym4n/smoke-shack/commit/b9c011392a8cb3f943a67701376dc31dfc30219d))
* delete cooks from history ([7fc8197](https://github.com/m3rrym4n/smoke-shack/commit/7fc81975459446cd060758ebd98536857d66ea24))
* end Masterbuilt startup at setpoint ([ed259ce](https://github.com/m3rrym4n/smoke-shack/commit/ed259ce95d950162c56ef0036188c6a94038ff34))
* list visible Home Assistant grills ([d7f44fd](https://github.com/m3rrym4n/smoke-shack/commit/d7f44fd731efdbb9a42cc4f6096d44281b393919))
* map Masterbuilt power to cook lifecycle ([1de2685](https://github.com/m3rrym4n/smoke-shack/commit/1de26858f35fc4c81bc4f3ddb520f5a7749eb87c))
* read samples from channel readings ([c608663](https://github.com/m3rrym4n/smoke-shack/commit/c6086638026a6dae7aa2827106cf7d15297d4cdc))
* read temperatures from connected grill channels ([b8fd8bf](https://github.com/m3rrym4n/smoke-shack/commit/b8fd8bfb6f2c9601cf0470b4af409a6d98013fd9))
* record samples as channel readings ([be37621](https://github.com/m3rrym4n/smoke-shack/commit/be376219a92d8163b4a7000ecf5643bafc9fb06e))
* replace pellets with typed fuel ([97c97f9](https://github.com/m3rrym4n/smoke-shack/commit/97c97f9ae472e52a1e77c58cae09d3985f4fb5d2))
* show connected grill pictures and identity ([ca449ae](https://github.com/m3rrym4n/smoke-shack/commit/ca449ae40d4801180193d39d4f120193e25b0e7c))
* show grill in cook log ([b66e05e](https://github.com/m3rrym4n/smoke-shack/commit/b66e05e22b546ec1f9235b2502374666885f4d39))
* show probe cards for connected grill channels ([1cd0389](https://github.com/m3rrym4n/smoke-shack/commit/1cd0389e9785e7b3ba2a8b854430e9b06d7d948d))
* store connected grill status entities ([416725f](https://github.com/m3rrym4n/smoke-shack/commit/416725f649b68363cd446a48e045f48dd2f7eff2))
* store pictures on equipment records ([db34f04](https://github.com/m3rrym4n/smoke-shack/commit/db34f0495c01623d20b2934359adb279904d1996))
* treat stale Masterbuilt telemetry as unknown ([44b7688](https://github.com/m3rrym4n/smoke-shack/commit/44b768863d71607a27229362aeb2d109bbbc6931))

## [1.3.5](https://github.com/m3rrym4n/smoke-shack/compare/v1.3.4...v1.3.5) (2026-11-04)


### Bug Fixes

* replace Home Assistant placeholder branding ([f729b81](https://github.com/m3rrym4n/smoke-shack/commit/f729b811382d40b4d1936c827206843291db1355))

## [1.3.4](https://github.com/m3rrym4n/smoke-shack/compare/v1.3.3...v1.3.4) (2026-11-02)


### Bug Fixes

* enable streaming ingress for backup restores ([6158189](https://github.com/m3rrym4n/smoke-shack/commit/6158189d70900093a4deef4c921bf3c861e1e959))

## [1.3.3](https://github.com/m3rrym4n/smoke-shack/compare/v1.3.2...v1.3.3) (2026-11-02)


### Bug Fixes

* collapse repeated leading request slashes ([9c534fa](https://github.com/m3rrym4n/smoke-shack/commit/9c534fa0a8b56a5db748fd3da92acd83ef138ddb))

## [1.3.2](https://github.com/m3rrym4n/smoke-shack/compare/v1.3.1...v1.3.2) (2026-11-02)


### Bug Fixes

* use app database path for migrations ([4f47439](https://github.com/m3rrym4n/smoke-shack/commit/4f474394430a34f437f187cab19a7c33bcf02b0b))

## [1.3.1](https://github.com/m3rrym4n/smoke-shack/compare/v1.3.0...v1.3.1) (2026-11-02)


### Bug Fixes

* make app data writable at startup ([c91d8b7](https://github.com/m3rrym4n/smoke-shack/commit/c91d8b757d85560e6039ea26e23691752fcd0a74))

# [1.3.0](https://github.com/m3rrym4n/smoke-shack/compare/v1.2.0...v1.3.0) (2026-11-01)


### Features

* add Home Assistant App wrapper ([1a5f99c](https://github.com/m3rrym4n/smoke-shack/commit/1a5f99c48ffacf915a4a30be7eab11c6e3d99c4a))
* add pellet pantry UPC and bag details ([e629e56](https://github.com/m3rrym4n/smoke-shack/commit/e629e565afb9a816a70656598f3049c433352754))
* add pellet UPC and bag size ([2205cf0](https://github.com/m3rrym4n/smoke-shack/commit/2205cf0639557eaae3b6be43c1a7a6bb957eb386))
* connect through Home Assistant Supervisor ([0d9edaf](https://github.com/m3rrym4n/smoke-shack/commit/0d9edaf6d25372edde8525fc2a73a060f650fca5))
* mark pellet bags empty ([f0bbe2d](https://github.com/m3rrym4n/smoke-shack/commit/f0bbe2d1debf64c29057fa09ddf7731dab590e5d))
* store Home Assistant App data under /data ([2745dda](https://github.com/m3rrym4n/smoke-shack/commit/2745dda61a6e65cc0c5c4b8f12105b15873d64ea))

# [1.2.0](https://github.com/m3rrym4n/smoke-shack/compare/v1.1.1...v1.2.0) (2026-11-01)


### Features

* support Home Assistant ingress path prefixes ([960c67d](https://github.com/m3rrym4n/smoke-shack/commit/960c67d7a9ddf097cf66aadf3bd66339ef206c19))

## [1.1.1](https://github.com/m3rrym4n/smoke-shack/compare/v1.1.0...v1.1.1) (2026-11-01)


### Bug Fixes

* include showcase images in backups ([e8272a5](https://github.com/m3rrym4n/smoke-shack/commit/e8272a5ed4abf79b1147a65ac218716c6cd52b0e))
* keep LAN address out of deploy test ([5e9ba84](https://github.com/m3rrym4n/smoke-shack/commit/5e9ba8432787ab5d062db57fbe178ddfe1d95feb))
* publish dev image as smoke-shack ([3c3b34d](https://github.com/m3rrym4n/smoke-shack/commit/3c3b34d883b07b0cd93b058c33cf78d25506f8e8))
* restore safety copy across filesystems ([ad2142c](https://github.com/m3rrym4n/smoke-shack/commit/ad2142c0312478f4a032366478c651bbcd257944))

# [1.1.0](http://192.168.1.73:3001/m3rrym4n/smoke-shack/compare/v1.0.2...v1.1.0) (2026-11-01)


### Bug Fixes

* restore deploy image and backup navigation ([02cf7e9](http://192.168.1.73:3001/m3rrym4n/smoke-shack/commit/02cf7e93acae0c02ad233b7b7c0a53684acede87))
* seed all default meat group types ([5a1179a](http://192.168.1.73:3001/m3rrym4n/smoke-shack/commit/5a1179a94caf4c35d6664493fc4d521247cad22c))
* update visible branding to Smoke-Shack ([64e874f](http://192.168.1.73:3001/m3rrym4n/smoke-shack/commit/64e874f09adc1497f76619451a484ec5f057608d))


### Features

* accept Smoke-Shack grill name variable ([5924e8e](http://192.168.1.73:3001/m3rrym4n/smoke-shack/commit/5924e8ef726ec09c0c383784f92aedadda4c7c38))
* add backup export API ([e09fc54](http://192.168.1.73:3001/m3rrym4n/smoke-shack/commit/e09fc54951af91d6ef6dc57daa17ea93a5e57fd1))
* add backup restore API ([f112123](http://192.168.1.73:3001/m3rrym4n/smoke-shack/commit/f112123275ed964d934ee04431ad1ec1b2c2ca08))
* add backup restore page ([42e1acf](http://192.168.1.73:3001/m3rrym4n/smoke-shack/commit/42e1acfc0cd0537f7f5a3a103d461ca2591737f1))
* add meat group management UI ([78dee8d](http://192.168.1.73:3001/m3rrym4n/smoke-shack/commit/78dee8d19b312e7d9af8a61d6c45f16c453cc1a9))
* add meat groups backend ([f08d768](http://192.168.1.73:3001/m3rrym4n/smoke-shack/commit/f08d7682e0b819f9960150c6bbf51dd7a9e51e40))
* show pitmaster cook-time confidence ([53e01af](http://192.168.1.73:3001/m3rrym4n/smoke-shack/commit/53e01af0d5a3a4a61195cbf01c4dffef65960ada))

## Unreleased

### Bug Fixes

* include the grill logo and picture in backup and restore archives
* keep the deployable dev image and move Backup & Restore into the main navigation
* update visible branding to Smoke-Shack

### Features

* add UPC, bag size, and computed bag cost to pellet records
* add UPC lookup and bag details to the Pellet Pantry
* support serving the frontend under a Home Assistant ingress path prefix
* add complete backup archive download API
* add validated in-place backup restore API with safety copies
* add Backup & Restore page for downloading and restoring archives
* add meat group CRUD and grouped cook statistics
* add meat group filtering and management to Ask the Pitmaster
* accept SMOKE_SHACK_GRILL_NAME with legacy variable fallback
* show cook-time ranges and low-confidence guidance in Ask the Pitmaster

## [1.0.2](http://192.168.1.73:3001/m3rrym4n/smoke-stack/compare/v1.0.1...v1.0.2) (2026-10-31)


### Bug Fixes

* backfill stable Forgejo releases ([5fd5137](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/5fd5137afadd0043ea0883d6b337132f00f2eb0c))

## [1.0.1](http://192.168.1.73:3001/m3rrym4n/smoke-stack/compare/v1.0.0...v1.0.1) (2026-10-28)


### Bug Fixes

* create Forgejo release without jq ([3e58ffa](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/3e58ffab9ba980462bc5f2061eb53702682b9ef9))
* stop release notes at top-level headings ([309019f](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/309019f8e99761ba2693e27b1445edd694f0a4dd))

# 1.0.0 (2026-10-28)


### Bug Fixes

* anchor smoke plume to grill photo ([e9b85bd](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/e9b85bd1487a3864da1bb7b5e0540a42b083e3c5))
* collapse brief Home Assistant data gaps ([c23fba5](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/c23fba521dfc8cb5f5ab828c02ed57fabe4ac2df))
* end chart ticks at cool-down ([883b57a](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/883b57aec3fb6a6016c2809613dd7c1b7a4e6294))
* handle grill restarts during cooldown ([a392f85](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/a392f8537542701f7c82aac6c43a9d8cfca67800))
* hide data gaps from cook log ([4c0f77e](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/4c0f77e26178311e530904c0dabffce9c73894df))
* ignore implausible grill snapshots ([9ff89e4](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/9ff89e4c8801494c1c05eb232d7e33ef00c18326))
* include butcher case meats in pitmaster filter ([e1dbeec](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/e1dbeec5b3841f4f152524f20c79d5cf630ba90f))
* install Docker CLI in build jobs ([3cee658](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/3cee658525af6f02f1f64c966ebde29156434b70))
* limit pin legend to share cards ([50c423d](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/50c423dab5d6cc6de2a0d6342b87cad452bbe3a3))
* make dev image write-back race-safe ([d370166](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/d370166ea9ad9f74c735e8da9802e7c96faf8931))
* merge cooked flag into spice rack ([67e192b](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/67e192baa5f1aa9ca4560d493316ef0560899b0e))
* move showcase logo into gauge ([fadfc7c](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/fadfc7c466653bd0e36bac38cca5502bb43571af))
* polish pit showcase picture editor ([4dab9ab](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/4dab9ab42d76953b17aa5cf47d97fe7d27373999))
* preserve cook chart probe target ([1d3a060](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/1d3a0602706d9d52f0c5ae1884218002d423b39b))
* preserve finished probe card targets ([6543ff8](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/6543ff8825761b0524b188d06f6f15327fd0fa9c))
* preserve share card chart styles ([aaf24f1](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/aaf24f1bd78ec351f64e0184b83102e5d52306b0))
* publish dev image and update compose tag ([c5bd0c3](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/c5bd0c3322caac72c4a8b540de489241bf688071))
* raise HA websocket message limit ([5041822](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/50418220846205302fa00d7d14526cf72eb0e026))
* rename health endpoint ([7d631d3](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/7d631d3bb33dc9dd5547beecf477f09be21e12b4))
* render realistic smoke above live page ([29a00f7](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/29a00f79bd4bb9cb3bb8e72b0c2c7db40a0cc3c3))
* retain samples with one unknown core state ([4cc71f7](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/4cc71f7e4ca99fb9462460d9d8ae9e69d8fd1c59))
* revalidate static frontend files ([d559996](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/d559996c58b75e8caa1ea919223724121b2b8902))
* safely accept SVG showcase logos ([76df29d](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/76df29df45ec55802609948903b7842ee5f27cd3))
* sample latest HA state on timer ([7d9e9e6](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/7d9e9e6831e9d51e5ba03a5c96417e4cf18c36c5))
* select live cook in pit notes ([9e997c4](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/9e997c464a4772a137c1bd92df97e17cc715c4da))
* shorten chart hour markers to axis ticks ([771a6fd](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/771a6fd514d3f5bd3a85a465c899c3c587ed018b))
* show live cooks in cook log ([d28c182](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/d28c1822ae5632f5e7c1e586e160902f2bf11a50))
* show new setpoint in event titles ([4265fe2](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/4265fe27e9715394410109618a0330d0292097ab))
* show pin legend on every chart ([7eff5ce](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/7eff5ce7d1a7eb74105dbf372f0b243985166c92))
* space finished cook chart labels ([31ea4c0](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/31ea4c0c02c8978822306e5e299d5f0bf1ba6d95))
* stack pit showcase vertically ([404f09d](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/404f09d60ae195a8d37fa754edc46548a1b5ca47))
* use real grill entities and states ([a5f17f4](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/a5f17f4157a3193f18a933e0f435e2dd69f982e9))
* use uv-managed Python in CI ([9be90e6](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/9be90e6524e411113b7577ba2ba079c71164b0b0))
* zero finished cook readings ([d50a0e6](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/d50a0e69c0e489b249b6efdd6722492c516e89a9))


### Features

* add Butcher Case purchase view ([18aec41](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/18aec41849044ff8535a6112fd5b96ea5ca3d5c3))
* add clock-hour chart markers ([0488436](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/04884367a390f28e8dad3817f766fbbf25c04423))
* add cook chart pin legend ([3eeeeac](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/3eeeeacc25395362f5dcdba3b85e91c9c8caa012))
* add cook charts and history ([fa17343](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/fa1734355ebfac4000b134b4132713a6c237a70b))
* add cook metadata edit and delete API ([a1d8104](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/a1d810463fa073378573954c8e9bb088b83a464c))
* add cook photo API ([f8208e8](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/f8208e8fb0c8db8486f1c5910b04c933389fc246))
* add cook photo galleries ([7e4c6a2](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/7e4c6a2724613558ef07953ee582f62422853b4c))
* add cook statistics API ([9415b5d](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/9415b5d76c9ef9131e239ab111b442a551cef7e6))
* add cook status badge to share card ([a82ff69](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/a82ff697aa2a975b28a394e482f78ee8bfd2b2c4))
* add cooked flag to meat ([70af2ea](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/70af2ea946ba85360ded5f625902b6de4e25c3dc))
* add CSV and JSON export API ([489ccfc](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/489ccfccd39e5d64946cee9c44cc7e46e86f86fd))
* add live cook forms ([fddb66a](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/fddb66ac4df4e1d29dcdcdc4faf225903a35dda4))
* add live cook view ([78a6670](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/78a6670e3323ef76398a3e4af71229673c41519f))
* add live smokestack animation ([665f82e](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/665f82e390b297f3fc16b10cec058fd516a6c388))
* add meat and pellets CRUD API ([a580942](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/a5809424caa268be034d5f75d1bbe8b54092fe46))
* add notes and user events API ([5ca08c2](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/5ca08c20b66d4ba4068714d758056aeb66b9cd57))
* add Order Pad cook modes ([92429af](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/92429af914c6af2bcf2c7415d844ae86ba0c171b))
* add pantry item photo APIs ([8b8cb5a](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/8b8cb5a4a100af1ca8e0bcc71e6bd9b6e10b270d))
* add pantry navigation shell ([c5d5af4](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/c5d5af4c573929efd4f086d6757d9a6e0f11bfc6))
* add pantry photo controls ([6648c2b](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/6648c2bd716c184a28588537b7ce14ffedc14ed2))
* add Pellet Pantry purchase view ([eb75522](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/eb75522cb54219459ce7d3876199cf2d99003c2c))
* add Pit Notes view ([d2f1edb](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/d2f1edb54d5162dd7c46c4053821106ae26571c2))
* add pit showcase API ([a850c39](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/a850c3908875550b2cabb55b1e0c25f9dd72e283))
* add pit showcase strip ([a015ac1](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/a015ac1362c896a89740487d97265e6edba8b73a))
* add pitmaster stats view ([ad64880](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/ad648809e70af314b2867aa2cb6998a6cfe5704f))
* add planned cook adoption ([e5be7f7](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/e5be7f7a3fa8da0de7f2632ec533b297d16b5093))
* add profiles CRUD API ([5834e68](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/5834e68070d5a7e56500ef3c886db04c30894b15))
* add runtime status visibility ([28db7d6](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/28db7d6c1a49b813f214bc117a8a06e0e103186c))
* add signage UI shell ([4fd5212](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/4fd5212c2f10ff3df913ca5b0638f83ca95109dd))
* add spice rack catalog API ([49e6446](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/49e64465c4c305cfda0ea99d6d6172c973bf38d1))
* add spice rack pantry view ([e2bf8e2](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/e2bf8e246591a0fb23d4b324737d1e7d5465e5f2))
* adopt semantic release versioning ([085ad5c](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/085ad5c5639d45a86c8bd01e1dbd8082b79f22cf))
* attach spices to cooks ([8ed6ce0](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/8ed6ce0452d79965145f2190cef466d6e8a0d030))
* choose cook photo for share card ([17f7156](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/17f7156c4292809438541398ad7a06727c815761))
* complete Order Pad inventory fields ([12dfc9e](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/12dfc9ee39e6853758b463eb838bfc27faec7fec))
* edit cooks from cook log ([57a593f](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/57a593f832d58d1aa6fbc6fd0073e36507108870))
* exclude test cooks from statistics ([b444203](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/b4442033b16c266f1159e4be9dfcf58224c2605d))
* export cook details as PNG ([8b226f2](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/8b226f25ee2e1bc3ad918b3508d3b39f503b36ab))
* pick spice rack rubs for cooks ([7061e60](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/7061e602b6d0f3d7d630c30df82ec7f15c671697))
* rebuild cook export as share card ([79ef9e2](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/79ef9e287030572c4659c0266e61445cf5f7f9ff))
* scaffold cook ingestion service ([fe8887f](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/fe8887fd63973d5a2819b79ccb9f2cc68861f3e5))
* show grill model and manufacturer ([d1e5976](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/d1e5976cb68cd9c1bd1607b4ad76ed4d073c5845))
* show notes on cook details ([eed0c19](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/eed0c191d05565c330ade048904b6dbc34916f53))
* simplify pitmaster filters ([9a0e551](http://192.168.1.73:3001/m3rrym4n/smoke-stack/commit/9a0e55166b7789584b5c4eae466d63cd51e834f1))

# Changelog

## Unreleased

- Adopt semantic-release for dev prereleases and main releases, and show the generated build version in the footer.
- Exclude marked dry-run and test cooks from all statistics while retaining them in logs and exports.
- Show the numbered pin legend below every cook chart.
- Add a numbered event legend below share-card charts.
- End finished-cook chart ticks at cool-down and remove clipped start and total-time labels.
- Space finished-cook target labels apart and keep late target labels clear of the chart edge.
- Show zero on the Pit gauge and unplugged probe cards after a cook finishes.
- Show the cook's startup, cooking, or complete status on share cards and cook details.
- Keep the final positive probe target on finished-cook charts and mark when it was reached.
- Add real clock-hour ticks on the x axis and cook start time to cook temperature charts.

- Pick multiple Spice Rack rubs on cook orders and show them across cook details, logs, and exports.
- Add the grouped, filterable Spice Rack with custom blend markers and rub create, edit, and delete controls.
- Add reusable photo upload, resize, thumbnail, lightbox, replace, and removal controls to every Pantry tab.
- Add secure photo uploads for pellet, meat, and spice pantry items.
- Consolidate Pellets and Meat under a responsive Pantry navigation shell.
- Add a seeded Meat Church spice rack catalog and CRUD API.
- Attach selected spice-rack entries to cooks and include them in cook exports.
- Mark Butcher Case purchases cooked or uncooked and filter the case by that status.
- Export a past cook as a fixed 1080×1350 Instagram-style share card with cook details, notes, results, a correctly styled chart, and a remembered gallery photo choice.
- Edit any planned, live, or closed cook and its photos from the Cook Log detail view.
- Show cook-linked notes on Cook Log detail views.
- Hide data-gap diagnostics from live and detail Cook Logs while retaining them in the API.
- Simplify Pitmaster filters to rotisserie yes/no and one pantry pellet choice.
- Revalidate frontend static files on every load so deployed UI changes appear immediately.
- Show the new grill temperature in setpoint-change event titles and the old value in details.
- Show the grill's Home Assistant device name or model with its manufacturer in The Pit.
- Collapse brief Home Assistant data gaps into one Cook Log summary.
- Anchor the smoke source and plume to the grill photo while the page scrolls.
- Move the showcase logo into the bottom of the temperature gauge.
- Render a realistic, state-aware smoke plume above the full live page with a demo mode.
- Make Pit showcase image selection row-specific and save smoke positions immediately.
- Stack the Pit showcase vertically with full-width, frameless grill photos and wrapping names.
- Accept safely validated SVG files for Pit showcase logos.
- List and default live and planned cooks correctly in Pit Notes.
- Add live-cook smokestack wisps with grill-state intensity and a remembered motion toggle.
- Add a responsive Pit showcase with grill branding, editable pictures, and a smoke anchor.
- Add the grill name and uploadable showcase logo and photo APIs.
- Show planned, live, and incomplete cooks in the Cook Log with automatic refreshes.
- Add immediate photo uploads and galleries to the Order Pad and cook details.
- Add explicit live, planned, new-order, and closed-cook modes to the Order Pad UI.
- Add planned cooks that are atomically adopted when the next live cook starts.
- Include uncooked Butcher Case meat types in the Ask the Pitmaster filter.
- Complete the Order Pad with available-purchase selectors, pellet usage, and cook costs.
- Add the Ask the Pitmaster cook-time statistics board with bookmarkable filters.
- Add the Pit Notes board with cook-aware create, filtering, inline edit, and delete controls.
- Add the Pellet Pantry purchase board with create, edit, linked-cook, and delete controls.
- Add the Butcher Case purchase board with create, edit, linked-cook, and delete controls.
- Preserve otherwise valid samples when only one core grill entity is unavailable.
- Prevent older dev builds from overwriting newer deployed image tags during CI write-back races.
- Sample the latest Home Assistant grill state on a timer while connected.
- Ignore implausible grill snapshots and coalesce Home Assistant update bursts.
- Add live event pinning and editing plus the cook Order Pad form.
- Add cook temperature charts, event logs, paginated cook history, and read-only cook details.
- Add the read-only live cook boards with pit gauge, phase progress, probes, and paused background polling.
- Add the BBQ signage UI shell, hash navigation, and active-cook neon indicator.
- Add filtered cook CSV, raw sample CSV, and full journal JSON export APIs.
- Add filtered cook duration statistics and meat-type count APIs.
- Add cook and event photo upload, serving, editing, listing, and deletion APIs.
- Add cook journal editing, linked summaries and costs, filtering, pagination, and deletion.
- Add profiles and ordered profile steps CRUD APIs.
- Add notes CRUD and editable user timeline event APIs.
- Add meat and pellet purchase CRUD APIs with filtering and cook reference protection.
- Raise the configurable HA websocket message limit and retain only configured entity states.
- Add runtime Home Assistant and active-cook visibility through logs and `GET /status`.
- Publish dev images to Zot and write the immutable tag back to `compose.yml`.
- Use the real gmg-ha entities and states for cook phases, warnings, and probe targets.
- Install the Docker CLI in image-build jobs and keep pull request runs build-only.
- Run CI quality checks with uv-managed Python 3.12 on Forgejo runners.
- Rename the health endpoint to `/health` across the app and deployment configuration.
- Scaffold the FastAPI service, persistent cook lifecycle, Home Assistant ingest,
  read API, database migration, container, and CI/CD skeleton.
