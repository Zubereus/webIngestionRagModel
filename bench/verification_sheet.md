# Retrieval gold draft verification sheet

All entries retain `TODO: verify`. No case is marked verified.

Run `python bench/verify_cases.py` to review cases interactively. Use `python bench/grep_snapshots.py "<regex>" [--url-contains X]` to search extracted Markdown; add `--fold` to ignore accents.

## Summary by type

- answerable: 36
- near_miss: 20
- off_topic: 3
- partial: 1

## Summary by set

- dev: 20
- holdout: 40

## Summary by site group

- Bo Cong an portal: answerable 17, near_miss 11, off_topic 2
- FastAPI docs: answerable 4, near_miss 5
- arXiv: answerable 15, near_miss 4, off_topic 1, partial 1

- Answerable cases with spans matching more than one snapshot page: 7
- Cases without an expected-page snapshot: 23

### Multi-page spans

- holdout-014: 3 pages; https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26279
- holdout-016: 2 pages; https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26247
- dev-013: 16 pages; https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26270
- dev-016: 3 pages; https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26256
- dev-017: 3 pages; https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26256
- dev-018: 4 pages; https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26276
- dev-020: 4 pages; https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26277

### Cases without snapshots

- holdout-009: What is the current retail price of an NVIDIA RTX 5090 in Vietnam?
- holdout-010: What uptime guarantee and support response time does FastAPI Cloud contractually promise?
- holdout-018: Tỷ giá USD/VND chính thức áp dụng hôm nay để quy đổi lệ phí thị thực là bao nhiêu?
- holdout-019: Hồ sơ của tôi tại tỉnh hiện được cán bộ nào xử lý và có số điện thoại cá nhân gì?
- holdout-020: Năm nay tỉnh nào có số lượt khách xuất nhập cảnh qua biên giới cao nhất?
- holdout-023: What numerical value of sigma did the autonomous-driving study use for the lane-divider potential?
- holdout-024: How many object queries are used by the YOLO27m transformer decoder?
- holdout-025: Which optimizer, learning rate, and training schedule were used for the YOLO27 experiments?
- holdout-026: What is the maximum request-body upload size enforced by FastAPI by default?
- holdout-027: What is the monthly price of the paid FastAPI Cloud plan?
- holdout-028: What is FastAPI Cloud's contractual uptime SLA and incident response time?
- holdout-029: Which OAuth provider and JWT expiration policy does the FastAPI example configure?
- holdout-030: How many simultaneous WebSocket connections are included in FastAPI Cloud's free tier?
- holdout-031: Hộ chiếu phổ thông cấp cho người từ đủ 14 tuổi có thời hạn sử dụng bao nhiêu năm?
- holdout-032: Phí chuyển phát hộ chiếu phổ thông về nhà tại tỉnh là bao nhiêu đồng?
- holdout-033: Thị thực điện tử Việt Nam cho phép người nước ngoài lưu trú tối đa bao nhiêu ngày?
- holdout-034: Ảnh tải lên khi xin thị thực điện tử phải có độ phân giải tối thiểu bao nhiêu pixel?
- holdout-035: Cơ sở lưu trú bị phạt bao nhiêu tiền nếu khai báo tạm trú cho khách nước ngoài chậm một ngày?
- holdout-036: Người dân có thể xin cấp hộ chiếu tại tỉnh khác nơi đăng ký thường trú hay không?
- holdout-037: Người nước ngoài đang ở Việt Nam phải nộp hồ sơ gì để gia hạn thị thực điện tử?
- holdout-038: Giấy phép xuất nhập cảnh cấp cho người không quốc tịch có giá trị trong bao nhiêu năm?
- holdout-039: Giấy thông hành biên giới Việt Nam–Lào được cấp có thời hạn tối đa bao lâu?
- holdout-040: Người xin thị thực điện tử cần nộp hồ sơ trước ngày nhập cảnh tối thiểu bao nhiêu ngày?

## Cases

### holdout-001 (holdout)

- Type: `answerable`
- Group: `arXiv`
- Question: What changes did YOLOv2 introduce to improve detection across object sizes?
- Expected URL: https://arxiv.org/html/2510.09653v4
- Snapshot: `data/raw/a446e1491fe7feae.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `through batch normalization, anchor boxes, dimension clustering, and multi-scale training` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://arxiv.org/html/2510.09653v4 ? Ultralytics YOLO Evolution: An Overview of YOLO27, YOLO26, YOLO11, YOLOv8, and YOLOv5 Object Detectors for Computer Vision and Pattern Recognition

### holdout-002 (holdout)

- Type: `answerable`
- Group: `FastAPI docs`
- Question: Which HTTP methods can be used to define a FastAPI path operation?
- Expected URL: https://fastapi.tiangolo.com/tutorial/first-steps
- Snapshot: `data/raw/94c74a9258b3dd5f.html` (exists: true)
- Status: `TODO: verify`
- Old span retained: `- `POST`: to create data.
- `GET`: to read data.`
- found_exact: `true`
- Span: `One of:
- `POST`
- `GET`
- `PUT`
- `DELETE`` (1 pages)
- Span: `...and the more exotic ones:
- `OPTIONS`
- `HEAD`
- `PATCH`
- `TRACE`` (1 pages)
- Acceptable URLs: none selected (`TODO: verify`)

### holdout-003 (holdout)

- Type: `answerable`
- Group: `arXiv`
- Question: Which three potential fields are combined for autonomous-vehicle path planning?
- Expected URL: https://arxiv.org/html/2306.06987v1
- Snapshot: `data/raw/4c40dbe48ced6234.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `the attractive PF, the road PF, and the obstacle PF` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://arxiv.org/html/2306.06987v1 ? Potential Field-based Path Planning with Interactive Speed Optimization for Autonomous Vehicles

### holdout-004 (holdout)

- Type: `answerable`
- Group: `arXiv`
- Question: How does the obstacle potential field help an autonomous vehicle?
- Expected URL: https://arxiv.org/html/2306.06987v1
- Snapshot: `data/raw/4c40dbe48ced6234.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `safety zone around the obstacle by assigning a high-risk value` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://arxiv.org/html/2306.06987v1 ? Potential Field-based Path Planning with Interactive Speed Optimization for Autonomous Vehicles

### holdout-005 (holdout)

- Type: `answerable`
- Group: `arXiv`
- Question: What information do vehicles share in the proposed interactive speed optimization approach?
- Expected URL: https://arxiv.org/html/2306.06987v1
- Snapshot: `data/raw/4c40dbe48ced6234.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `shared local path via V2V communication for cooperative driving` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://arxiv.org/html/2306.06987v1 ? Potential Field-based Path Planning with Interactive Speed Optimization for Autonomous Vehicles

### holdout-006 (holdout)

- Type: `answerable`
- Group: `FastAPI docs`
- Question: Which URL opens FastAPI's interactive API documentation after starting the example server?
- Expected URL: https://fastapi.tiangolo.com/tutorial/first-steps
- Snapshot: `data/raw/94c74a9258b3dd5f.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `http://127.0.0.1:8000/docs` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://fastapi.tiangolo.com/tutorial/first-steps/ ? First Steps¶

### holdout-007 (holdout)

- Type: `answerable`
- Group: `FastAPI docs`
- Question: Which URL opens the alternative ReDoc documentation interface?
- Expected URL: https://fastapi.tiangolo.com/tutorial/first-steps
- Snapshot: `data/raw/94c74a9258b3dd5f.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `http://127.0.0.1:8000/redoc` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://fastapi.tiangolo.com/tutorial/first-steps/ ? First Steps¶

### holdout-008 (holdout)

- Type: `answerable`
- Group: `FastAPI docs`
- Question: What does the OpenAPI schema describe about a FastAPI application?
- Expected URL: https://fastapi.tiangolo.com/tutorial/first-steps
- Snapshot: `data/raw/94c74a9258b3dd5f.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `This schema definition includes your API paths, the possible parameters` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://fastapi.tiangolo.com/tutorial/first-steps/ ? First Steps¶

### holdout-009 (holdout)

- Type: `off_topic`
- Group: `arXiv`
- Question: What is the current retail price of an NVIDIA RTX 5090 in Vietnam?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `RTX\s*5090|NVIDIA.{0,30}price|price.{0,30}NVIDIA`
- Top keyword-overlap pages:
  - https://arxiv.org/html/2510.09653v4 (overlap 3)
  - https://arxiv.org/html/2306.06987v1 (overlap 1)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121796 (overlap 0)
- Candidate snapshot evidence:
  - https://arxiv.org/html/2510.09653v4: age self-attention for global-context modeling. Preliminary COCO results span 42.3-60.4 mAP at 640-pixel resolution and 0.62-2.32 ms TensorRT 11 FP16 latency, with YOLO27l reaching 61.2 mAP at 800 pixels. The evolution is subsequently traced through YOLO26, i…
  - https://arxiv.org/html/2510.09653v4: ults span 42.3-60.4 mAP at 640-pixel resolution and 0.62-2.32 ms TensorRT 11 FP16 latency, with YOLO27l reaching 61.2 mAP at 800 pixels. The evolution is subsequently traced through YOLO26, including DFL removal, Progressive Loss Balancing, Small-Target-Aware…
  - https://arxiv.org/html/2510.09653v4: es ranging from 42.3 for YOLO27n to 60.4 for YOLO27l, with TensorRT 11 FP16 GPU inference latency ranging from approximately 0.62 ms to 2.32 ms on an NVIDIA RTX PRO 6000. YOLO27l additionally reaches 61.2 mAP at 800-pixel resolution. These preliminary measure…

### holdout-010 (holdout)

- Type: `near_miss`
- Group: `FastAPI docs`
- Question: What uptime guarantee and support response time does FastAPI Cloud contractually promise?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `uptime|SLA|support.{0,40}response|FastAPI Cloud`
- Top keyword-overlap pages:
  - https://fastapi.tiangolo.com/tutorial/first-steps/ (overlap 4)
  - https://arxiv.org/html/2510.09653v4 (overlap 3)
  - https://en.wikipedia.org/wiki/Retrieval-augmented_generation (overlap 3)
- Candidate snapshot evidence:
  - https://fastapi.tiangolo.com/tutorial/first-steps/: # First Steps¶ The simplest FastAPI file could look like this: ``` from fastapi import FastAPI app = FastAPI() @app.get("/") async def root(): return {"message": "He
  - https://fastapi.tiangolo.com/tutorial/first-steps/: ncluding a path operation explorer, path operation search, CodeLens navigation in tests (jump to definition from tests), and FastAPI Cloud deployment and logs, all from your editor. Run the live server: ``` $ uv run fastapi dev FastAPI Starting development ser
  - https://fastapi.tiangolo.com/tutorial/first-steps/: to definition from tests), and FastAPI Cloud deployment and logs, all from your editor. Run the live server: ``` $ uv run fastapi dev FastAPI Starting development server 🚀 Searching for package file structure from directories with __

### holdout-011 (holdout)

- Type: `answerable`
- Group: `Bo Cong an portal`
- Question: Cơ sở lưu trú cần khai báo tạm trú cho người nước ngoài vào thời điểm nào?
- Expected URL: https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26265
- Snapshot: `data/raw/3d3938290fcc6a14.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `khai báo ngay khi người nước ngoài đến đăng ký tạm trú.` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26265 ? Khai báo tạm trú cho người nước ngoài tại Việt Nam qua Trang thông tin điện tử

### holdout-012 (holdout)

- Type: `answerable`
- Group: `Bo Cong an portal`
- Question: Trang khai báo tạm trú trực tuyến hoạt động theo khung thời gian nào?
- Expected URL: https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26265
- Snapshot: `data/raw/3d3938290fcc6a14.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `24 giờ/07 ngày Trực tuyến qua Trang thông tin điện tử` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26265 ? Khai báo tạm trú cho người nước ngoài tại Việt Nam qua Trang thông tin điện tử

### holdout-013 (holdout)

- Type: `answerable`
- Group: `Bo Cong an portal`
- Question: Người nước ngoài tự đề nghị cấp thị thực điện tử cần khai theo mẫu nào?
- Expected URL: https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26277
- Snapshot: `data/raw/912b9748fea473ae.html` (exists: true)
- Status: `TODO: verify`
- Old span retained: `an) theo mẫu NA1a ban hành kèm theo`
- found_exact: `true`
- Span: `mẫu NA1a` (1 pages)
- Acceptable URLs: none selected (`TODO: verify`)

### holdout-014 (holdout)

- Type: `answerable`
- Group: `Bo Cong an portal`
- Question: Người xin giấy miễn thị thực cần chứng minh điều kiện quan hệ gia đình hoặc nguồn gốc nào?
- Expected URL: https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26279
- Snapshot: `data/raw/c9972798b5d0c4c6.html` (exists: true)
- Status: `TODO: verify`
- Old span retained: `ngoài là vợ, chồng, con của người Việt Nam định`
- found_exact: `true`
- Span: `vợ, chồng, con của người Việt Nam định cư ở nước ngoài` (3 pages)
- Other pages containing span(s):
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26249 ? Cấp lại giấy miễn thị thực tại Cục Quản lý xuất nhập cảnh, Bộ Công an
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=35700 ? Gia hạn tạm trú cho người đã được cấp giấy miễn thị thực tại Phòng Quản lý xuất nhập cảnh Công an tỉnh, thành phố trực thuộc Trung ương
- Acceptable URLs: none selected (`TODO: verify`)

### holdout-015 (holdout)

- Type: `answerable`
- Group: `Bo Cong an portal`
- Question: Tờ khai xin cấp giấy miễn thị thực có mã mẫu nào?
- Expected URL: https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26279
- Snapshot: `data/raw/c9972798b5d0c4c6.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `Mẫu NA9` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26279 ? Cấp giấy miễn thị thực cho người Việt Nam định cư ở nước ngoài và người nước ngoài là vợ, chồng, con của người Việt Nam định cư ở nước ngoài hoặc của công dân Việt Nam

### holdout-016 (holdout)

- Type: `answerable`
- Group: `Bo Cong an portal`
- Question: Lệ phí cấp giấy phép xuất nhập cảnh cho người không quốc tịch là bao nhiêu?
- Expected URL: https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26247
- Snapshot: `data/raw/f2ab4093fbbd6bce.html` (exists: true)
- Status: `TODO: verify`
- Old span retained: `đủ hồ sơ.

Không

- 200.000đ

| Tên giấy`
- found_exact: `true`
- Span: `200.000đ` (2 pages)
- Other pages containing span(s):
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26245 ? Cấp lại giấy phép xuất nhập cảnh cho người không quốc tịch cư trú tại Việt Nam
- Acceptable URLs: none selected (`TODO: verify`)

### holdout-017 (holdout)

- Type: `answerable`
- Group: `Bo Cong an portal`
- Question: Cơ quan, tổ chức tại Việt Nam phải đăng nhập tài khoản ở đâu để đề nghị cấp thị thực điện tử?
- Expected URL: https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26276
- Snapshot: `data/raw/8ce915c2b7b4b9f3.html` (exists: true)
- Status: `TODO: verify`
- Old span retained: `miền tiếng Việt là “https://xuatnhapcanh.gov.vn”, tiếng Anh là “https://immigration.gov.vn”),`
- found_exact: `true`
- Span: `https://xuatnhapcanh.gov.vn` (1 pages)
- Acceptable URLs: none selected (`TODO: verify`)

### holdout-018 (holdout)

- Type: `near_miss`
- Group: `Bo Cong an portal`
- Question: Tỷ giá USD/VND chính thức áp dụng hôm nay để quy đổi lệ phí thị thực là bao nhiêu?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `tỷ giá|VND|đồng Việt Nam`
- Top keyword-overlap pages:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26277 (overlap 9)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26248 (overlap 8)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26249 (overlap 8)
- Candidate snapshot evidence:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=35699: g Bộ Công an và nêu rõ lý do. + Thời gian trả kết quả: Từ thứ 2 đến thứ 6 hàng tuần (trừ ngày Tết, ngày lễ). - Trực tiếp - *5 Ngày làm việc* nộp hồ sơ trực tiếp tại trụ sở Cơ quan Quản lý xuất nhập cảnh Công an cấp tỉnh. Trong thời hạn 03 ngày làm việc kể từ …
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=35699: Trực tiếp - *5 Ngày làm việc* nộp hồ sơ trực tiếp tại trụ sở Cơ quan Quản lý xuất nhập cảnh Công an cấp tỉnh. Trong thời hạn 03 ngày làm việc kể từ ngày nhận đủ hồ sơ, Phòng Quản lý xuất nhập cảnh Công an tỉnh, thành phố trực thuộc trung ương xem xét và chuyể…
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=35699: cảnh về Cục Quản lý xuất nhập cảnh. Cục Quản lý xuất nhập cảnh xem xét cấp, cấp lại giấy phép xuất nhập cảnh trong thời hạn 02 ngày làm việc. Trực tuyến - *5 Ngày làm việc* nộp hồ sơ trực tuyến qua Cổng dịch vụ công quốc gia hoặc Cổng dịch vụ công Bộ Công an.…

### holdout-019 (holdout)

- Type: `off_topic`
- Group: `Bo Cong an portal`
- Question: Hồ sơ của tôi tại tỉnh hiện được cán bộ nào xử lý và có số điện thoại cá nhân gì?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `cán bộ|điện thoại|hồ sơ`
- Top keyword-overlap pages:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121796 (overlap 4)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121936 (overlap 4)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26245 (overlap 4)
- Candidate snapshot evidence:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121796: văn bản và nêu rõ lý do. + Thời gian nhận kết quả: từ thứ 2 đến thứ 6 hàng tuần (trừ ngày Tết, ngày lễ). - **Trực tiếp** - *03 Ngày làm việc* Nộp hồ sơ trực tiếp tại Cơ quan Quản lý xuất nhập cảnh Công an tỉnh nơi thường trú. + Thời hạn giải quyết: 03 ngày là…
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121796: an tỉnh nơi thường trú. + Thời hạn giải quyết: 03 ngày làm việc kể từ ngày nhận đủ hồ sơ theo quy định. - **Trực tuyến** - *03 Ngày làm việc* Nộp hồ sơ trực tuyến qua Cổng Dịch vụ công quốc gia hoặc Cổng Dịch vụ công Bộ Công an. - Thời hạn giải quyết: 03 ngày…
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121796: công Bộ Công an. - Thời hạn giải quyết: 03 ngày làm việc kể từ ngày nhận đủ hồ sơ theo quy định. **Lệ phí :** 50.000 Đồng (50.000đ/giấy thông hành (Thông tư số 25/2021/TT-BTC ngày 07/4/2021 của Bộ Tài chính).) **Lệ phí :** 25.000 Đồng (25.000.000đ/giấy thông …

### holdout-020 (holdout)

- Type: `off_topic`
- Group: `Bo Cong an portal`
- Question: Năm nay tỉnh nào có số lượt khách xuất nhập cảnh qua biên giới cao nhất?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `lượt khách|xuất nhập cảnh|biên giới`
- Top keyword-overlap pages:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26270 (overlap 9)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121796 (overlap 8)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121936 (overlap 8)
- Candidate snapshot evidence:
  - https://arxiv.org/html/2306.06987v1: hnology*, vol. 66, no. 2, pp. 952–964, Feb. 2017. - \[11\] H. Wang, Y. Huang, A. Khajepour, Y. Zhang, Y. Rasekhipour, and D. Cao, “Crash mitigation in motion planning for autonomous vehicles,” *IEEE Transactions on Intelligent Transportation Systems*, vol. 20…
  - https://arxiv.org/html/2306.06987v1: Intelligent Transportation Systems*, vol. 20, no. 9, pp. 3313–3323, Sep. 2019. - \[12\] H. Wang, Y. Huang, A. Khajepour, D. Cao, and C. Lv, “Ethical Decision-Making platform in autonomous vehicles with lexicographic optimization based model predictive control…
  - https://arxiv.org/html/2306.06987v1: ” *IEEE Transactions on Intelligent Transportation Systems*, pp. 1–17, 2022. - \[16\] J. Wang, Y. Yan, K. Zhang, Y. Chen, M. Cao, and G. Yin, “Path planning on large curvature roads using Driver-Vehicle-Road system based on the kinematic vehicle model,” *IEEE…

### holdout-021 (holdout)

- Type: `answerable`
- Group: `arXiv`
- Question: How many parameters does the YOLO27n checkpoint contain?
- Expected URL: https://arxiv.org/html/2510.09653v4
- Snapshot: `data/raw/a446e1491fe7feae.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `3.0 million parameters` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://arxiv.org/html/2510.09653v4 ? Ultralytics YOLO Evolution: An Overview of YOLO27, YOLO26, YOLO11, YOLOv8, and YOLOv5 Object Detectors for Computer Vision and Pattern Recognition

### holdout-022 (holdout)

- Type: `partial`
- Group: `arXiv`
- Question: What exact GPU and batch size were used to measure YOLO27 inference latency?
- Expected URL: https://arxiv.org/html/2510.09653v4
- Snapshot: `data/raw/a446e1491fe7feae.html` (exists: true)
- Status: `TODO: verify`
- Check patterns: `batch[- ]?size|RTX PRO 6000|GPU inference latency`
- Top keyword-overlap pages:
  - https://arxiv.org/html/2510.09653v4 (overlap 8)
  - https://en.wikipedia.org/wiki/Retrieval-augmented_generation (overlap 2)
  - https://arxiv.org/html/2306.06987v1 (overlap 1)
- Candidate snapshot evidence:
  - https://arxiv.org/html/2510.09653v4: age self-attention for global-context modeling. Preliminary COCO results span 42.3-60.4 mAP at 640-pixel resolution and 0.62-2.32 ms TensorRT 11 FP16 latency, with YOLO27l reaching 61.2 mAP at 800 pixels. The evolution is subsequently traced through YOLO26, i…
  - https://arxiv.org/html/2510.09653v4: ults span 42.3-60.4 mAP at 640-pixel resolution and 0.62-2.32 ms TensorRT 11 FP16 latency, with YOLO27l reaching 61.2 mAP at 800 pixels. The evolution is subsequently traced through YOLO26, including DFL removal, Progressive Loss Balancing, Small-Target-Aware…
  - https://arxiv.org/html/2510.09653v4: es ranging from 42.3 for YOLO27n to 60.4 for YOLO27l, with TensorRT 11 FP16 GPU inference latency ranging from approximately 0.62 ms to 2.32 ms on an NVIDIA RTX PRO 6000. YOLO27l additionally reaches 61.2 mAP at 800-pixel resolution. These preliminary measure…

### holdout-023 (holdout)

- Type: `near_miss`
- Group: `arXiv`
- Question: What numerical value of sigma did the autonomous-driving study use for the lane-divider potential?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `sigma|lane.?divider|potential.{0,30}field`
- Top keyword-overlap pages:
  - https://arxiv.org/html/2306.06987v1 (overlap 9)
  - https://arxiv.org/html/2510.09653v4 (overlap 5)
  - https://en.wikipedia.org/wiki/Retrieval-augmented_generation (overlap 4)
- Candidate snapshot evidence:
  - https://arxiv.org/html/2306.06987v1: # Potential Field-based Path Planning with Interactive Speed Optimization for Autonomous Vehicles ###### Abstract Path planning is critical for
  - https://arxiv.org/html/2306.06987v1: g is critical for autonomous vehicles (AVs) to determine the optimal route while considering constraints and objectives. The potential field (PF) approach has become prevalent in path planning due to its simple structure and computational efficiency. However,…
  - https://arxiv.org/html/2306.06987v1: ’ PFs by slowing down in advance, effectively reducing the oscillations for both ego and obstacle AVs. ###### Index Terms: Autonomous vehicle, path planning, potential field, optimization, collision avoidance, V2V communication ## I Introduction Due to the su…

### holdout-024 (holdout)

- Type: `near_miss`
- Group: `arXiv`
- Question: How many object queries are used by the YOLO27m transformer decoder?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `YOLO27m.{0,50}(query|decoder)|object queries|query.{0,30}decoder`
- Top keyword-overlap pages:
  - https://arxiv.org/html/2510.09653v4 (overlap 7)
  - https://docs.python.org/3/tutorial/errors.html (overlap 3)
  - https://arxiv.org/html/2306.06987v1 (overlap 2)
- Candidate snapshot evidence:
  - https://arxiv.org/html/2510.09653v4: age self-attention for global-context modeling. Preliminary COCO results span 42.3-60.4 mAP at 640-pixel resolution and 0.62-2.32 ms TensorRT 11 FP16 latency, with YOLO27l reaching 61.2 mAP at 800 pixels. The evolution is subsequently traced through YOLO26, i…
  - https://arxiv.org/html/2510.09653v4: ults span 42.3-60.4 mAP at 640-pixel resolution and 0.62-2.32 ms TensorRT 11 FP16 latency, with YOLO27l reaching 61.2 mAP at 800 pixels. The evolution is subsequently traced through YOLO26, including DFL removal, Progressive Loss Balancing, Small-Target-Aware…
  - https://arxiv.org/html/2510.09653v4: es ranging from 42.3 for YOLO27n to 60.4 for YOLO27l, with TensorRT 11 FP16 GPU inference latency ranging from approximately 0.62 ms to 2.32 ms on an NVIDIA RTX PRO 6000. YOLO27l additionally reaches 61.2 mAP at 800-pixel resolution. These preliminary measure…

### holdout-025 (holdout)

- Type: `near_miss`
- Group: `arXiv`
- Question: Which optimizer, learning rate, and training schedule were used for the YOLO27 experiments?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `optimizer|learning rate|training schedule|epochs`
- Top keyword-overlap pages:
  - https://arxiv.org/html/2510.09653v4 (overlap 7)
  - https://arxiv.org/html/2306.06987v1 (overlap 3)
  - https://docs.python.org/3/tutorial/errors.html (overlap 2)
- Candidate snapshot evidence:
  - https://arxiv.org/html/2510.09653v4: age self-attention for global-context modeling. Preliminary COCO results span 42.3-60.4 mAP at 640-pixel resolution and 0.62-2.32 ms TensorRT 11 FP16 latency, with YOLO27l reaching 61.2 mAP at 800 pixels. The evolution is subsequently traced through YOLO26, i…
  - https://arxiv.org/html/2510.09653v4: ults span 42.3-60.4 mAP at 640-pixel resolution and 0.62-2.32 ms TensorRT 11 FP16 latency, with YOLO27l reaching 61.2 mAP at 800 pixels. The evolution is subsequently traced through YOLO26, including DFL removal, Progressive Loss Balancing, Small-Target-Aware…
  - https://arxiv.org/html/2510.09653v4: es ranging from 42.3 for YOLO27n to 60.4 for YOLO27l, with TensorRT 11 FP16 GPU inference latency ranging from approximately 0.62 ms to 2.32 ms on an NVIDIA RTX PRO 6000. YOLO27l additionally reaches 61.2 mAP at 800-pixel resolution. These preliminary measure…

### holdout-026 (holdout)

- Type: `near_miss`
- Group: `arXiv`
- Question: What is the maximum request-body upload size enforced by FastAPI by default?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `upload size|request body|request.{0,30}size|maximum.{0,30}size`
- Top keyword-overlap pages:
  - https://arxiv.org/html/2510.09653v4 (overlap 3)
  - https://fastapi.tiangolo.com/tutorial/first-steps/ (overlap 2)
  - https://arxiv.org/html/2306.06987v1 (overlap 1)
- Candidate snapshot evidence:
  - https://arxiv.org/html/2510.09653v4: age self-attention for global-context modeling. Preliminary COCO results span 42.3-60.4 mAP at 640-pixel resolution and 0.62-2.32 ms TensorRT 11 FP16 latency, with YOLO27l reaching 61.2 mAP at 800 pixels. The evolution is subsequently traced through YOLO26, i…
  - https://arxiv.org/html/2510.09653v4: ults span 42.3-60.4 mAP at 640-pixel resolution and 0.62-2.32 ms TensorRT 11 FP16 latency, with YOLO27l reaching 61.2 mAP at 800 pixels. The evolution is subsequently traced through YOLO26, including DFL removal, Progressive Loss Balancing, Small-Target-Aware…
  - https://arxiv.org/html/2510.09653v4: es ranging from 42.3 for YOLO27n to 60.4 for YOLO27l, with TensorRT 11 FP16 GPU inference latency ranging from approximately 0.62 ms to 2.32 ms on an NVIDIA RTX PRO 6000. YOLO27l additionally reaches 61.2 mAP at 800-pixel resolution. These preliminary measure…

### holdout-027 (holdout)

- Type: `near_miss`
- Group: `FastAPI docs`
- Question: What is the monthly price of the paid FastAPI Cloud plan?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `FastAPI Cloud.{0,50}(price|plan)|\$\s?\d+|monthly`
- Top keyword-overlap pages:
  - https://fastapi.tiangolo.com/tutorial/first-steps/ (overlap 2)
  - https://arxiv.org/html/2306.06987v1 (overlap 1)
  - https://arxiv.org/html/2510.09653v4 (overlap 1)
- Candidate snapshot evidence:
  - https://fastapi.tiangolo.com/tutorial/first-steps/: # First Steps¶ The simplest FastAPI file could look like this: ``` from fastapi import FastAPI app = FastAPI() @app.get("/") async def root(): return {"message": "He
  - https://fastapi.tiangolo.com/tutorial/first-steps/: ncluding a path operation explorer, path operation search, CodeLens navigation in tests (jump to definition from tests), and FastAPI Cloud deployment and logs, all from your editor. Run the live server: ``` $ uv run fastapi dev FastAPI Starting development ser
  - https://fastapi.tiangolo.com/tutorial/first-steps/: to definition from tests), and FastAPI Cloud deployment and logs, all from your editor. Run the live server: ``` $ uv run fastapi dev FastAPI Starting development server 🚀 Searching for package file structure from directories with __

### holdout-028 (holdout)

- Type: `near_miss`
- Group: `FastAPI docs`
- Question: What is FastAPI Cloud's contractual uptime SLA and incident response time?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `uptime|SLA|incident response|support response`
- Top keyword-overlap pages:
  - https://fastapi.tiangolo.com/tutorial/first-steps/ (overlap 4)
  - https://arxiv.org/html/2510.09653v4 (overlap 2)
  - https://en.wikipedia.org/wiki/Retrieval-augmented_generation (overlap 2)
- Candidate snapshot evidence:
  - https://fastapi.tiangolo.com/tutorial/first-steps/: # First Steps¶ The simplest FastAPI file could look like this: ``` from fastapi import FastAPI app = FastAPI() @app.get("/") async def root(): return {"message": "He
  - https://fastapi.tiangolo.com/tutorial/first-steps/: ncluding a path operation explorer, path operation search, CodeLens navigation in tests (jump to definition from tests), and FastAPI Cloud deployment and logs, all from your editor. Run the live server: ``` $ uv run fastapi dev FastAPI Starting development ser
  - https://fastapi.tiangolo.com/tutorial/first-steps/: to definition from tests), and FastAPI Cloud deployment and logs, all from your editor. Run the live server: ``` $ uv run fastapi dev FastAPI Starting development server 🚀 Searching for package file structure from directories with __

### holdout-029 (holdout)

- Type: `near_miss`
- Group: `FastAPI docs`
- Question: Which OAuth provider and JWT expiration policy does the FastAPI example configure?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `OAuth|JWT|expiration|token lifetime`
- Top keyword-overlap pages:
  - https://fastapi.tiangolo.com/tutorial/first-steps/ (overlap 4)
  - https://arxiv.org/html/2510.09653v4 (overlap 1)
  - https://docs.python.org/3/tutorial/errors.html (overlap 1)
- Candidate snapshot evidence:
  - https://fastapi.tiangolo.com/tutorial/first-steps/: # First Steps¶ The simplest FastAPI file could look like this: ``` from fastapi import FastAPI app = FastAPI() @app.get("/") async def root(): return {"message": "He
  - https://fastapi.tiangolo.com/tutorial/first-steps/: ncluding a path operation explorer, path operation search, CodeLens navigation in tests (jump to definition from tests), and FastAPI Cloud deployment and logs, all from your editor. Run the live server: ``` $ uv run fastapi dev FastAPI Starting development ser
  - https://fastapi.tiangolo.com/tutorial/first-steps/: to definition from tests), and FastAPI Cloud deployment and logs, all from your editor. Run the live server: ``` $ uv run fastapi dev FastAPI Starting development server 🚀 Searching for package file structure from directories with __

### holdout-030 (holdout)

- Type: `near_miss`
- Group: `FastAPI docs`
- Question: How many simultaneous WebSocket connections are included in FastAPI Cloud's free tier?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `WebSocket|simultaneous connections|free tier`
- Top keyword-overlap pages:
  - https://fastapi.tiangolo.com/tutorial/first-steps/ (overlap 5)
  - https://arxiv.org/html/2510.09653v4 (overlap 4)
  - https://docs.python.org/3/tutorial/errors.html (overlap 3)
- Candidate snapshot evidence:
  - https://fastapi.tiangolo.com/tutorial/first-steps/: # First Steps¶ The simplest FastAPI file could look like this: ``` from fastapi import FastAPI app = FastAPI() @app.get("/") async def root(): return {"message": "He
  - https://fastapi.tiangolo.com/tutorial/first-steps/: ncluding a path operation explorer, path operation search, CodeLens navigation in tests (jump to definition from tests), and FastAPI Cloud deployment and logs, all from your editor. Run the live server: ``` $ uv run fastapi dev FastAPI Starting development ser
  - https://fastapi.tiangolo.com/tutorial/first-steps/: to definition from tests), and FastAPI Cloud deployment and logs, all from your editor. Run the live server: ``` $ uv run fastapi dev FastAPI Starting development server 🚀 Searching for package file structure from directories with __

### holdout-031 (holdout)

- Type: `near_miss`
- Group: `Bo Cong an portal`
- Question: Hộ chiếu phổ thông cấp cho người từ đủ 14 tuổi có thời hạn sử dụng bao nhiêu năm?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `giá trị sử dụng|thời hạn.{0,40}(năm|tháng)`
- Top keyword-overlap pages:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26256 (overlap 9)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26270 (overlap 9)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=29497 (overlap 9)
- Candidate snapshot evidence:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26256: in trong hồ sơ của người gửi. + Thời gian trả kết quả: Từ thứ 2 đến thứ 6 hàng tuần (trừ ngày Tết, ngày lễ). - Trực tiếp - *01 Ngày làm việc* 01 ngày làm việc kể từ khi nhận đơn trình báo mất hộ chiếu phổ thông, Cục Quản lý xuất nhập cảnh hủy giá trị sử dụng …
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26256: chiếu cho người gửi đơn. Trực tiếp nộp hồ sơ tại trụ sở làm việc của Cục Quản lý xuất nhập cảnh - Bộ Công an. Trực tuyến - *1 Ngày làm việc* 01 ngày làm việc kể từ khi nhận đơn trình báo mất hộ chiếu phổ thông, Cục Quản lý xuất nhập cảnh hủy giá trị sử dụng h…
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26256: o người gửi đơn. Nộp hồ sơ trực tuyến qua Cổng Dịch vụ công quốc gia hoặc Cổng dịch vụ công Bộ Công an. Dịch vụ bưu chính - *01 Ngày làm việc* 01 ngày làm việc kể từ khi nhận đơn trình báo mất hộ chiếu phổ thông, Cục Quản lý xuất nhập cảnh hủy giá trị sử dụng…

### holdout-032 (holdout)

- Type: `near_miss`
- Group: `Bo Cong an portal`
- Question: Phí chuyển phát hộ chiếu phổ thông về nhà tại tỉnh là bao nhiêu đồng?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `chuyển phát|bưu chính|cước`
- Top keyword-overlap pages:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26245 (overlap 8)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26247 (overlap 8)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26248 (overlap 8)
- Candidate snapshot evidence:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26496: i tác tại Việt Nam. Sau khi thực hiện bước này, người nước ngoài sẽ được hệ thống cấp mã hồ sơ điện tử. Thời gian nộp hồ sơ: 24giờ/07 ngày Bước 2: Nhận kết quả + Người nước ngoài sử dụng mã hồ sơ điện tử để kiểm tra kết quả giải quyết tại Trang giao dịch điện…
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26496: trả lời đề nghị cấp thị thực tại cửa khẩu quốc tế. + Thời gian: từ thứ 2 đến thứ 6 (trừ ngày Tết, ngày lễ) - Trực tuyến - *02 Ngày làm việc* Nộp hồ sơ trực tuyến qua Trang giao dịch điện tử tại Cổng thông tin điện tử về xuất nhập cảnh hoặc Cổng dịch vụ công q…
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26496: i Cổng thông tin điện tử về xuất nhập cảnh hoặc Cổng dịch vụ công quốc gia hoặc Cổng dịch vụ công Bộ Công an. Trong thời hạn 02 ngày làm việc kể từ ngày nhận đủ hồ sơ theo quy định, Cục Quản lý xuất nhập cảnh chuyển cơ quan được Chính phủ giao chủ trì triển k…

### holdout-033 (holdout)

- Type: `near_miss`
- Group: `Bo Cong an portal`
- Question: Thị thực điện tử Việt Nam cho phép người nước ngoài lưu trú tối đa bao nhiêu ngày?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `90 ngày|lưu trú|tối đa`
- Top keyword-overlap pages:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26245 (overlap 9)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26247 (overlap 9)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26248 (overlap 9)
- Candidate snapshot evidence:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26265: ông an. - Bước 4: Kiểm tra thông tin đã khai báo tạm trú trên hệ thống và hoàn thành việc khai báo tạm trú. - Trực tuyến - *24 giờ/07 ngày* Trực tuyến qua Trang thông tin điện tử hoặc Cổng dịch vụ công quốc gia hoặc Cổng dịch vụ công Bộ Công an. Không Không |…
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26265: tra thông tin đã khai báo tạm trú trên hệ thống và hoàn thành việc khai báo tạm trú. ## Thời hạn giải quyết Trực tuyến 24 giờ/07 ngày Trực tuyến qua Trang thông tin điện tử hoặc Cổng dịch vụ công quốc gia hoặc Cổng dịch vụ công Bộ Công an. ## Phí Không ##
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26265: ### LĨNH VỰC TTHC #### Khai báo tạm trú cho người nước ngoài tại Việt Nam qua Trang thông tin điện tử Công an Tỉnh - **Trực tuyến** - Bước 1: Người khai báo tạm trú đăng ký tài khoản kha

### holdout-034 (holdout)

- Type: `near_miss`
- Group: `Bo Cong an portal`
- Question: Ảnh tải lên khi xin thị thực điện tử phải có độ phân giải tối thiểu bao nhiêu pixel?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `pixel|px|độ phân giải`
- Top keyword-overlap pages:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=29497 (overlap 8)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121796 (overlap 7)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121936 (overlap 7)
- Candidate snapshot evidence:
  - https://arxiv.org/html/2510.09653v4: age self-attention for global-context modeling. Preliminary COCO results span 42.3-60.4 mAP at 640-pixel resolution and 0.62-2.32 ms TensorRT 11 FP16 latency, with YOLO27l reaching 61.2 mAP at 800 pixels. The evolution is subsequently traced through YOLO26, i…
  - https://arxiv.org/html/2510.09653v4: ults span 42.3-60.4 mAP at 640-pixel resolution and 0.62-2.32 ms TensorRT 11 FP16 latency, with YOLO27l reaching 61.2 mAP at 800 pixels. The evolution is subsequently traced through YOLO26, including DFL removal, Progressive Loss Balancing, Small-Target-Aware…
  - https://arxiv.org/html/2510.09653v4: es ranging from 42.3 for YOLO27n to 60.4 for YOLO27l, with TensorRT 11 FP16 GPU inference latency ranging from approximately 0.62 ms to 2.32 ms on an NVIDIA RTX PRO 6000. YOLO27l additionally reaches 61.2 mAP at 800-pixel resolution. These preliminary measure…

### holdout-035 (holdout)

- Type: `near_miss`
- Group: `Bo Cong an portal`
- Question: Cơ sở lưu trú bị phạt bao nhiêu tiền nếu khai báo tạm trú cho khách nước ngoài chậm một ngày?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `phạt|xử phạt`
- Top keyword-overlap pages:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26245 (overlap 9)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26247 (overlap 9)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26248 (overlap 9)
- Candidate snapshot evidence:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26265: ông an. - Bước 4: Kiểm tra thông tin đã khai báo tạm trú trên hệ thống và hoàn thành việc khai báo tạm trú. - Trực tuyến - *24 giờ/07 ngày* Trực tuyến qua Trang thông tin điện tử hoặc Cổng dịch vụ công quốc gia hoặc Cổng dịch vụ công Bộ Công an. Không Không |…
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26265: tra thông tin đã khai báo tạm trú trên hệ thống và hoàn thành việc khai báo tạm trú. ## Thời hạn giải quyết Trực tuyến 24 giờ/07 ngày Trực tuyến qua Trang thông tin điện tử hoặc Cổng dịch vụ công quốc gia hoặc Cổng dịch vụ công Bộ Công an. ## Phí Không ##
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26265: ### LĨNH VỰC TTHC #### Khai báo tạm trú cho người nước ngoài tại Việt Nam qua Trang thông tin điện tử Công an Tỉnh - **Trực tuyến** - Bước 1: Người khai báo tạm trú đă

### holdout-036 (holdout)

- Type: `near_miss`
- Group: `Bo Cong an portal`
- Question: Người dân có thể xin cấp hộ chiếu tại tỉnh khác nơi đăng ký thường trú hay không?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `bất kỳ|nơi thường trú|nơi tạm trú|tỉnh khác`
- Top keyword-overlap pages:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121936 (overlap 10)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26248 (overlap 10)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26249 (overlap 10)
- Candidate snapshot evidence:
  - https://arxiv.org/html/2510.09653v4: age self-attention for global-context modeling. Preliminary COCO results span 42.3-60.4 mAP at 640-pixel resolution and 0.62-2.32 ms TensorRT 11 FP16 latency, with YOLO27l reaching 61.2 mAP at 800 pixels. The evolution is subsequently traced through YOLO26, i…
  - https://arxiv.org/html/2510.09653v4: ults span 42.3-60.4 mAP at 640-pixel resolution and 0.62-2.32 ms TensorRT 11 FP16 latency, with YOLO27l reaching 61.2 mAP at 800 pixels. The evolution is subsequently traced through YOLO26, including DFL removal, Progressive Loss Balancing, Small-Target-Aware…
  - https://arxiv.org/html/2510.09653v4: es ranging from 42.3 for YOLO27n to 60.4 for YOLO27l, with TensorRT 11 FP16 GPU inference latency ranging from approximately 0.62 ms to 2.32 ms on an NVIDIA RTX PRO 6000. YOLO27l additionally reaches 61.2 mAP at 800-pixel resolution. These preliminary measure…

### holdout-037 (holdout)

- Type: `near_miss`
- Group: `Bo Cong an portal`
- Question: Người nước ngoài đang ở Việt Nam phải nộp hồ sơ gì để gia hạn thị thực điện tử?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `gia hạn thị thực`
- Top keyword-overlap pages:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121936 (overlap 11)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26248 (overlap 11)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26249 (overlap 11)
- Candidate snapshot evidence:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121936: n bản và nêu rõ lý do. \+ Thời gian nhận kết quả: từ thứ 2 đến thứ 6 hàng tuần (trừ ngày Tết, ngày lễ). - **Trực tiếp** - *03 Ngày làm việc* Nộp hồ sơ trực tiếp tại Cơ quan Quản lý xuất nhập cảnh Công an cấp tỉnh nơi cơ quan, tổ chức, doanh nghiệp người đó là…
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121936: Ngày làm việc* Nộp hồ sơ trực tuyến qua Cổng Dịch vụ công quốc gia hoặc Cổng Dịch vụ công Bộ Công an. - Thời hạn giải quyết: 03 ngày làm việc kể từ ngày nhận đủ hồ sơ theo quy định. Lệ phí : 50.000đ/giấy thông hành (Thông tư số 25/2021/TT-BTC ngày 07/4/2021 c…
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121936: do. + Thời gian nhận kết quả: từ thứ 2 đến thứ 6 hàng tuần (trừ ngày Tết, ngày lễ). ## Thời hạn giải quyết Trực tiếp 03 Ngày làm việc Nộp hồ sơ trực tiếp tại Cơ quan Quản lý xuất nhập cảnh Công an cấp tỉnh nơi cơ quan, tổ chức, doanh nghiệp người đó làm việc.

### holdout-038 (holdout)

- Type: `near_miss`
- Group: `Bo Cong an portal`
- Question: Giấy phép xuất nhập cảnh cấp cho người không quốc tịch có giá trị trong bao nhiêu năm?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `giá trị sử dụng|thời hạn.{0,40}(năm|tháng)`
- Top keyword-overlap pages:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26249 (overlap 12)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26279 (overlap 12)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121796 (overlap 11)
- Candidate snapshot evidence:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26249: g Bộ Công an và nêu rõ lý do. + Thời gian trả kết quả: Từ thứ 2 đến thứ 6 hàng tuần (trừ ngày Tết, ngày lễ). - Trực tiếp - *5 Ngày* nộp hồ sơ trực tiếp tại trụ sở Cục Quản lý xuất nhập cảnh không quá 05 ngày làm việc kể từ ngày nhận đủ hồ sơ. Trực tuyến - *5 …
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26249: ng tuần (trừ ngày Tết, ngày lễ). - Trực tiếp - *5 Ngày* nộp hồ sơ trực tiếp tại trụ sở Cục Quản lý xuất nhập cảnh không quá 05 ngày làm việc kể từ ngày nhận đủ hồ sơ. Trực tuyến - *5 Ngày* nộp hồ sơ trực tuyến qua Cổng dịch vụ công quốc gia hoặc Cổng dịch vụ …
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26249: ông báo của Cục Quản lý xuất nhập cảnh trên Cổng dịch vụ công quốc gia hoặc Cổng dịch vụ công Bộ Công an (nếu có). không quá 05 ngày làm việc kể từ ngày nhận đủ hồ sơ. 10 USD Không | Tên giấy tờ | Mẫu đơn, tờ khai | Số lượng | |---|---|---| | Hộ chiếu hoặc gi…

### holdout-039 (holdout)

- Type: `near_miss`
- Group: `Bo Cong an portal`
- Question: Giấy thông hành biên giới Việt Nam–Lào được cấp có thời hạn tối đa bao lâu?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `giá trị sử dụng|thời hạn.{0,40}(năm|tháng)`
- Top keyword-overlap pages:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121796 (overlap 11)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121936 (overlap 11)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=35694 (overlap 11)
- Candidate snapshot evidence:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121796: văn bản và nêu rõ lý do. + Thời gian nhận kết quả: từ thứ 2 đến thứ 6 hàng tuần (trừ ngày Tết, ngày lễ). - **Trực tiếp** - *03 Ngày làm việc* Nộp hồ sơ trực tiếp tại Cơ quan Quản lý xuất nhập cảnh Công an tỉnh nơi thường trú. + Thời hạn giải quyết: 03 ngày là…
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121796: an tỉnh nơi thường trú. + Thời hạn giải quyết: 03 ngày làm việc kể từ ngày nhận đủ hồ sơ theo quy định. - **Trực tuyến** - *03 Ngày làm việc* Nộp hồ sơ trực tuyến qua Cổng Dịch vụ công quốc gia hoặc Cổng Dịch vụ công Bộ Công an. - Thời hạn giải quyết: 03 ngày…
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121796: công Bộ Công an. - Thời hạn giải quyết: 03 ngày làm việc kể từ ngày nhận đủ hồ sơ theo quy định. **Lệ phí :** 50.000 Đồng (50.000đ/giấy thông hành (Thông tư số 25/2021/TT-BTC ngày 07/4/2021 của Bộ Tài chính).) **Lệ phí :** 25.000 Đồng (25.000.000đ/giấy thông …

### holdout-040 (holdout)

- Type: `near_miss`
- Group: `Bo Cong an portal`
- Question: Người xin thị thực điện tử cần nộp hồ sơ trước ngày nhập cảnh tối thiểu bao nhiêu ngày?
- Expected URL: (none)
- Snapshot: `(none)` (exists: false)
- Status: `TODO: verify`
- Check patterns: `trước.{0,30}ngày`
- Top keyword-overlap pages:
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121936 (overlap 8)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26249 (overlap 8)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26270 (overlap 8)
- Candidate snapshot evidence:
  - https://arxiv.org/html/2510.09653v4: age self-attention for global-context modeling. Preliminary COCO results span 42.3-60.4 mAP at 640-pixel resolution and 0.62-2.32 ms TensorRT 11 FP16 latency, with YOLO27l reaching 61.2 mAP at 800 pixels. The evolution is subsequently traced through YOLO26, i…
  - https://arxiv.org/html/2510.09653v4: ults span 42.3-60.4 mAP at 640-pixel resolution and 0.62-2.32 ms TensorRT 11 FP16 latency, with YOLO27l reaching 61.2 mAP at 800 pixels. The evolution is subsequently traced through YOLO26, including DFL removal, Progressive Loss Balancing, Small-Target-Aware…
  - https://arxiv.org/html/2510.09653v4: es ranging from 42.3 for YOLO27n to 60.4 for YOLO27l, with TensorRT 11 FP16 GPU inference latency ranging from approximately 0.62 ms to 2.32 ms on an NVIDIA RTX PRO 6000. YOLO27l additionally reaches 61.2 mAP at 800-pixel resolution. These preliminary measure…

### dev-001 (dev)

- Type: `answerable`
- Group: `arXiv`
- Question: How does YOLO27 use different architectures for its small and large model sizes?
- Expected URL: https://arxiv.org/html/2510.09653v4
- Snapshot: `data/raw/a446e1491fe7feae.html` (exists: true)
- Status: `TODO: verify`
- Old span retained: `strategy. The compact YOLO27n and YOLO27s detection models retain an efficiency-oriented`
- found_exact: `true`
- Span: `The compact YOLO27n and YOLO27s detection models retain an efficiency-oriented CNN pathway` (1 pages)
- Span: `the higher-capacity YOLO27m and YOLO27l detectors transition toward query-based prediction with transformer decoding` (1 pages)
- Acceptable URLs: none selected (`TODO: verify`)

### dev-002 (dev)

- Type: `answerable`
- Group: `arXiv`
- Question: What training strategy improves foreground alignment in compact YOLO27 detectors?
- Expected URL: https://arxiv.org/html/2510.09653v4
- Snapshot: `data/raw/a446e1491fe7feae.html` (exists: true)
- Status: `TODO: verify`
- Old span retained: `strengthened high-resolution features, foreground-alignment supervision, and conventional or NMS-free`
- found_exact: `true`
- Span: `training-time foreground alignment` (1 pages)
- Acceptable URLs: none selected (`TODO: verify`)

### dev-003 (dev)

- Type: `answerable`
- Group: `arXiv`
- Question: What architecture do YOLO27 medium and large variants use?
- Expected URL: https://arxiv.org/html/2510.09653v4
- Snapshot: `data/raw/a446e1491fe7feae.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `YOLO27m retains a CNN-oriented backbone` (1 pages)
- Span: `YOLO27l introduces the UltraViT backbone` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://arxiv.org/html/2510.09653v4 ? Ultralytics YOLO Evolution: An Overview of YOLO27, YOLO26, YOLO11, YOLOv8, and YOLOv5 Object Detectors for Computer Vision and Pattern Recognition

### dev-004 (dev)

- Type: `answerable`
- Group: `arXiv`
- Question: What is YOLO26's key change to Distribution Focal Loss?
- Expected URL: https://arxiv.org/html/2510.09653v4
- Snapshot: `data/raw/a446e1491fe7feae.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `YOLO26 removes Distribution Focal Loss (DFL), supports native end-to-end NMS-free inference` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://arxiv.org/html/2510.09653v4 ? Ultralytics YOLO Evolution: An Overview of YOLO27, YOLO26, YOLO11, YOLOv8, and YOLOv5 Object Detectors for Computer Vision and Pattern Recognition

### dev-005 (dev)

- Type: `answerable`
- Group: `arXiv`
- Question: Which training methods accompany YOLO26's NMS-free design?
- Expected URL: https://arxiv.org/html/2510.09653v4
- Snapshot: `data/raw/a446e1491fe7feae.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `Progressive Loss Balancing and Small-Target-Aware Label assignment` (1 pages)
- Span: `MuSGD blends SGD with Muon-style curvature/momentum for fast, smooth convergence` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://arxiv.org/html/2510.09653v4 ? Ultralytics YOLO Evolution: An Overview of YOLO27, YOLO26, YOLO11, YOLOv8, and YOLOv5 Object Detectors for Computer Vision and Pattern Recognition

### dev-006 (dev)

- Type: `answerable`
- Group: `arXiv`
- Question: How does YOLO11 balance detection accuracy and device efficiency?
- Expected URL: https://arxiv.org/html/2510.09653v4
- Snapshot: `data/raw/a446e1491fe7feae.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `better FLOPs-to-mAP ratios on mainstream GPUs and edge SoCs` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://arxiv.org/html/2510.09653v4 ? Ultralytics YOLO Evolution: An Overview of YOLO27, YOLO26, YOLO11, YOLOv8, and YOLOv5 Object Detectors for Computer Vision and Pattern Recognition

### dev-007 (dev)

- Type: `answerable`
- Group: `arXiv`
- Question: Why did YOLOv8 introduce a decoupled detection head?
- Expected URL: https://arxiv.org/html/2510.09653v4
- Snapshot: `data/raw/a446e1491fe7feae.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `The decoupled head separates classification and regression branches` (1 pages)
- Span: `mitigating gradient interference between localization and recognition objectives` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://arxiv.org/html/2510.09653v4 ? Ultralytics YOLO Evolution: An Overview of YOLO27, YOLO26, YOLO11, YOLOv8, and YOLOv5 Object Detectors for Computer Vision and Pattern Recognition

### dev-008 (dev)

- Type: `answerable`
- Group: `arXiv`
- Question: How did YOLOv5 encourage adoption among Python developers?
- Expected URL: https://arxiv.org/html/2510.09653v4
- Snapshot: `data/raw/a446e1491fe7feae.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `fully PyTorch-native implementation, catalyzing adoption by unifying training utilities` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://arxiv.org/html/2510.09653v4 ? Ultralytics YOLO Evolution: An Overview of YOLO27, YOLO26, YOLO11, YOLOv8, and YOLOv5 Object Detectors for Computer Vision and Pattern Recognition

### dev-009 (dev)

- Type: `answerable`
- Group: `arXiv`
- Question: What does mAP at IoU thresholds from 0.50 to 0.95 measure on COCO?
- Expected URL: https://arxiv.org/html/2510.09653v4
- Snapshot: `data/raw/a446e1491fe7feae.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `across multiple intersection-over-union thresholds ($0.50$ to $0.95$) quantifies detection quality` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://arxiv.org/html/2510.09653v4 ? Ultralytics YOLO Evolution: An Overview of YOLO27, YOLO26, YOLO11, YOLOv8, and YOLOv5 Object Detectors for Computer Vision and Pattern Recognition

### dev-010 (dev)

- Type: `answerable`
- Group: `arXiv`
- Question: In object detection, what do precision and recall measure?
- Expected URL: https://arxiv.org/html/2510.09653v4
- Snapshot: `data/raw/a446e1491fe7feae.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `Precision measures the fraction of predicted boxes that match ground truth` (1 pages)
- Span: `recall quantifies the fraction of ground-truth objects that are detected` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://arxiv.org/html/2510.09653v4 ? Ultralytics YOLO Evolution: An Overview of YOLO27, YOLO26, YOLO11, YOLOv8, and YOLOv5 Object Detectors for Computer Vision and Pattern Recognition

### dev-011 (dev)

- Type: `answerable`
- Group: `Bo Cong an portal`
- Question: Thời hạn giải quyết cấp hộ chiếu phổ thông ở cấp trung ương là bao lâu?
- Expected URL: https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26270
- Snapshot: `data/raw/b3b800f9d0533e5c.html` (exists: true)
- Status: `TODO: verify`
- Old span retained: `Không quá 03 ngày làm việc kể từ`
- found_exact: `true`
- Span: `Không quá 05 ngày làm việc kể từ ngày nhận đầy đủ hồ sơ theo quy định.` (1 pages)
- Span: `Không quá 03 ngày làm việc kể từ ngày nhận đầy đủ hồ sơ theo quy định đối với các trường hợp quy định tại khoản 4 Điều 15 Luật xuất cảnh, nhập cảnh của công dân Việt Nam.` (1 pages)
- Acceptable URLs: none selected (`TODO: verify`)

### dev-012 (dev)

- Type: `answerable`
- Group: `Bo Cong an portal`
- Question: Cấp hộ chiếu phổ thông ở cấp tỉnh mất bao nhiêu ngày làm việc?
- Expected URL: https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=29497
- Snapshot: `data/raw/b0223ad6b55747eb.html` (exists: true)
- Status: `TODO: verify`
- Old span retained: `*08 Ngày làm việc* nộp hồ sơ`
- found_exact: `true`
- Span: `08 Ngày làm việc` (1 pages)
- Acceptable URLs: none selected (`TODO: verify`)

### dev-013 (dev)

- Type: `answerable`
- Group: `Bo Cong an portal`
- Question: Thủ tục cấp hộ chiếu ở cấp trung ương có mất lệ phí không?
- Expected URL: https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26270
- Snapshot: `data/raw/b3b800f9d0533e5c.html` (exists: true)
- Status: `TODO: verify`
- Section path contains: `Lệ Phí`
- Old span retained: `## Lệ Phí

Không

## Thành phần hồ sơ`
- found_exact: `true`
- Span: `Không` (16 pages)
- Other pages containing span(s):
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26256 ? Trình báo mất hộ chiếu phổ thông (thực hiện tại cấp trung ương)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=29497 ? Cấp hộ chiếu phổ thông ở trong nước (thực hiện tại cấp tỉnh)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26276 ? Cấp thị thực điện tử theo đề nghị của cơ quan, tổ chức
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26265 ? Khai báo tạm trú cho người nước ngoài tại Việt Nam qua Trang thông tin điện tử
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26692 ? Thủ tục: Kiểm tra, xét duyệt nhân sự, cấp phép nhập cảnh cho người nước ngoài nhập cảnh vào Việt Nam qua giao dịch điện tử tại Cổng thông tin điện tử về xuất nhập cảnh
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26496 ? Xét duyệt nhân sự cấp phép nhập cảnh cho người nước ngoài nhập cảnh vào Việt Nam theo điều ước quốc tế mà Việt Nam là thành viên nhưng chưa có hiện diện thương mại hoặc đối tác tại Việt Nam
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26279 ? Cấp giấy miễn thị thực cho người Việt Nam định cư ở nước ngoài và người nước ngoài là vợ, chồng, con của người Việt Nam định cư ở nước ngoài hoặc của công dân Việt Nam
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26249 ? Cấp lại giấy miễn thị thực tại Cục Quản lý xuất nhập cảnh, Bộ Công an
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26248 ? Gia hạn tạm trú cho người đã được cấp giấy miễn thị thực tại Cục Quản lý xuất nhập cảnh Bộ Công an
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=35700 ? Gia hạn tạm trú cho người đã được cấp giấy miễn thị thực tại Phòng Quản lý xuất nhập cảnh Công an tỉnh, thành phố trực thuộc Trung ương
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121796 ? Cấp giấy thông hành biên giới Việt Nam – Lào cho công dân Việt Nam có hộ khẩu thường trú ở tỉnh có chung đường biên giới với Lào (thực hiện tại cấp tỉnh)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=121936 ? Cấp giấy thông hành biên giới Việt Nam – Lào cho công dân Việt Nam làm việc trong các cơ quan, tổ chức, doanh nghiệp có trụ sở tại tỉnh có chung đường biên giới với Lào
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=35694 ? Trình báo mất giấy thông hành (thực hiện tại cấp tỉnh)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=64187 ? Trình báo mất giấy thông hành (thực hiện tại cấp xã)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=35714 ? Trình báo mất hộ chiếu phổ thông (thực hiện tại cấp tỉnh)
- Acceptable URLs: none selected (`TODO: verify`)

### dev-014 (dev)

- Type: `answerable`
- Group: `Bo Cong an portal`
- Question: Trẻ dưới 14 tuổi chưa có mã số định danh cần giấy tờ gì để xin hộ chiếu ở cấp tỉnh?
- Expected URL: https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=29497
- Snapshot: `data/raw/b0223ad6b55747eb.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `Bản sao giấy khai sinh hoặc trích lục giấy khai sinh` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=29497 ? Cấp hộ chiếu phổ thông ở trong nước (thực hiện tại cấp tỉnh)

### dev-015 (dev)

- Type: `answerable`
- Group: `Bo Cong an portal`
- Question: Người chưa đủ 14 tuổi dùng mẫu tờ khai hộ chiếu nào?
- Expected URL: https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=29497
- Snapshot: `data/raw/b0223ad6b55747eb.html` (exists: true)
- Status: `TODO: verify`
- Old span retained: `tuổi trở lên; mẫu TK01a dành cho người chưa`
- found_exact: `true`
- Span: `mẫu TK01a dành cho người chưa đủ 14 tuổi` (1 pages)
- Acceptable URLs: none selected (`TODO: verify`)

### dev-016 (dev)

- Type: `answerable`
- Group: `Bo Cong an portal`
- Question: Người bị mất hộ chiếu phải gửi đơn trình báo trong thời hạn bao lâu?
- Expected URL: https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26256
- Snapshot: `data/raw/68da930c6c6d2e4f.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `thời hạn 02 ngày làm việc kể từ` (3 pages)
- Other pages containing span(s):
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26496 ? Xét duyệt nhân sự cấp phép nhập cảnh cho người nước ngoài nhập cảnh vào Việt Nam theo điều ước quốc tế mà Việt Nam là thành viên nhưng chưa có hiện diện thương mại hoặc đối tác tại Việt Nam
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=35714 ? Trình báo mất hộ chiếu phổ thông (thực hiện tại cấp tỉnh)
- Acceptable URLs (TODO: verify):
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26256 ? Trình báo mất hộ chiếu phổ thông (thực hiện tại cấp trung ương)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=35714 ? Trình báo mất hộ chiếu phổ thông (thực hiện tại cấp tỉnh)

### dev-017 (dev)

- Type: `answerable`
- Group: `Bo Cong an portal`
- Question: Đơn trình báo mất hộ chiếu phổ thông sử dụng mẫu nào?
- Expected URL: https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26256
- Snapshot: `data/raw/68da930c6c6d2e4f.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `hộ chiếu phổ thông (mẫu TK05) ban hành` (3 pages)
- Other pages containing span(s):
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=64187 ? Trình báo mất giấy thông hành (thực hiện tại cấp xã)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=35714 ? Trình báo mất hộ chiếu phổ thông (thực hiện tại cấp tỉnh)
- Acceptable URLs (TODO: verify):
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26256 ? Trình báo mất hộ chiếu phổ thông (thực hiện tại cấp trung ương)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=35714 ? Trình báo mất hộ chiếu phổ thông (thực hiện tại cấp tỉnh)

### dev-018 (dev)

- Type: `answerable`
- Group: `Bo Cong an portal`
- Question: Thị thực điện tử do cơ quan, tổ chức đề nghị được giải quyết trong bao lâu?
- Expected URL: https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26276
- Snapshot: `data/raw/8ce915c2b7b4b9f3.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `Không quá 03 ngày làm việc kể từ` (4 pages)
- Other pages containing span(s):
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26270 ? Cấp hộ chiếu phổ thông ở trong nước (thực hiện tại cấp trung ương)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26277 ? Cấp thị thực điện tử theo đề nghị của người nước ngoài
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26692 ? Thủ tục: Kiểm tra, xét duyệt nhân sự, cấp phép nhập cảnh cho người nước ngoài nhập cảnh vào Việt Nam qua giao dịch điện tử tại Cổng thông tin điện tử về xuất nhập cảnh
- Acceptable URLs (TODO: verify):
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26276 ? Cấp thị thực điện tử theo đề nghị của cơ quan, tổ chức

### dev-019 (dev)

- Type: `answerable`
- Group: `Bo Cong an portal`
- Question: Lệ phí thị thực điện tử một lần và nhiều lần theo đề nghị của tổ chức là bao nhiêu?
- Expected URL: https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26276
- Snapshot: `data/raw/8ce915c2b7b4b9f3.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `25USD/một thị thực giá trị một lần` (1 pages)
- Span: `50USD/một thị thực giá trị nhiều lần` (1 pages)
- Acceptable URLs (TODO: verify):
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26276 ? Cấp thị thực điện tử theo đề nghị của cơ quan, tổ chức

### dev-020 (dev)

- Type: `answerable`
- Group: `Bo Cong an portal`
- Question: Người nước ngoài tự đề nghị cấp thị thực điện tử mất bao lâu?
- Expected URL: https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26277
- Snapshot: `data/raw/912b9748fea473ae.html` (exists: true)
- Status: `TODO: verify`
- found_exact: `true`
- Span: `Không quá 03 ngày làm việc kể từ` (4 pages)
- Other pages containing span(s):
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26270 ? Cấp hộ chiếu phổ thông ở trong nước (thực hiện tại cấp trung ương)
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26276 ? Cấp thị thực điện tử theo đề nghị của cơ quan, tổ chức
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26692 ? Thủ tục: Kiểm tra, xét duyệt nhân sự, cấp phép nhập cảnh cho người nước ngoài nhập cảnh vào Việt Nam qua giao dịch điện tử tại Cổng thông tin điện tử về xuất nhập cảnh
- Acceptable URLs (TODO: verify):
  - https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26277 ? Cấp thị thực điện tử theo đề nghị của người nước ngoài
