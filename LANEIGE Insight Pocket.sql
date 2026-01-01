CREATE TABLE `라네즈 제품 상세 스냅샷` (
	`id`	BIGINT	NOT NULL,
	`snapshot_time`	TIMESTAMP	NOT NULL,
	`name`	TEXT	NOT NULL,
	`product_url`	TEXT	NOT NULL,
	`price`	DECIMAL(10, 2)	NOT NULL,
	`review_count`	BIGINT	NOT NULL	DEFAULT 0,
	`rating`	DECIMAL(10, 2)	NULL,
	`rating_5_pct`	BIGINT	NOT NULL	DEFAULT 0,
	`rating_4_pct`	BIGINT	NOT NULL	DEFAULT 0,
	`rating_3_pct`	BIGINT	NOT NULL	DEFAULT 0,
	`rating_2_pct`	BIGINT	NOT NULL	DEFAULT 0,
	`rating_1_pct`	BIGINT	NOT NULL	DEFAULT 0,
	`last_month_sales`	BIGINT	NOT NULL	DEFAULT 0,
	`style`	TEXT	NULL,
	`rank_1`	BIGINT	NOT NULL	DEFAULT 0,
	`rank_1_category`	VARCHAR	NOT NULL,
	`rank_2`	BIGINT	NOT NULL	DEFAULT 0,
	`rank_2_category`	VARCHAR	NOT NULL,
	`custemoers_say`	TEXT	NOT NULL
);

CREATE TABLE `베스트셀러 카테고리` (
	`id`	BIGINT	NOT NULL,
	`code`	VARCHAR	NOT NULL,
	`name`	VARCHAR	NOT NULL,
	`sort_order`	BIGINT	NOT NULL
);

CREATE TABLE `스냅샷 내 TOP 30 아이템` (
	`id`	BIGINT	NOT NULL,
	`snapshot_id`	BIGINT	NOT NULL,
	`rank`	BIGINT	NOT NULL,
	`product_name`	TEXT	NOT NULL,
	`price`	DECIMAL(10, 2)	NOT NULL,
	`is_laneige`	BOOLEAN	NOT NULL,
	`created_at`	TIMESTAMP	NOT NULL
);

CREATE TABLE `카테고리별 스냅샷 헤더` (
	`id`	BIGINT	NOT NULL,
	`snapshot_time`	TIMESTAMP	NOT NULL,
	`category_id`	BIGINT	NOT NULL,
	`created_at`	TIMESTAMP	NOT NULL
);

ALTER TABLE `라네즈 제품 상세 스냅샷` ADD CONSTRAINT `PK_라네즈 제품 상세 스냅샷` PRIMARY KEY (
	`id`
);

ALTER TABLE `베스트셀러 카테고리` ADD CONSTRAINT `PK_베스트셀러 카테고리` PRIMARY KEY (
	`id`
);

ALTER TABLE `스냅샷 내 TOP 30 아이템` ADD CONSTRAINT `PK_스냅샷 내 TOP 30 아이템` PRIMARY KEY (
	`id`
);

ALTER TABLE `카테고리별 스냅샷 헤더` ADD CONSTRAINT `PK_카테고리별 스냅샷 헤더` PRIMARY KEY (
	`id`
);

