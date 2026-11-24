# 적응형 보정 규칙 v0.1

실측 최적화 전의 초기값이다. 성능 향상을 보장하지 않는다. 튜닝용 클립으로 결정하고 최종 평가 클립에서는 고정한다.
BGR uint8 → Y=0.114B+0.587G+0.299R. brightness=Y 평균, contrast=Y 표준편차.
라플라시안 커널은 [[0,1,0],[1,-4,1],[0,1,0]], 반사 패딩을 NumPy로 직접 구현한다.
sharpness=내부 라플라시안 분산. noise=MAD(L)/(0.67448975×√20).
3픽셀 미만 영상에서는 전체 라플라시안을 쓴다. noise는 가우시안 잡음의 근사 추정이며 질감·빗줄기와 잡음을 완전히 분리하지 못한다.

| ID | 조건 | 변경 |
|---|---|---|
| BR_DARK | brightness < 60 | gamma=0.5 |
| BR_DIM | 60 ≤ brightness < 100 | gamma=0.75 |
| BR_BRIGHT | brightness > 190 | gamma=1.3 |
| CT_LOW | contrast < 35 AND noise < 8 | hist_eq=true |
| NS_HIGH | noise ≥ 18 | denoise=median, ksize=5 |
| NS_MEDIUM | 8 ≤ noise < 18 | denoise=gaussian, ksize=3 |
| SH_LOW | sharpness < 100 AND noise < 8 | unsharp=0.8 |

기본값: gamma=1.0, hist_eq=false, denoise=none, ksize=3, unsharp=0.0.
규칙 ID 기록 순서는 밝기 → 대비 → 잡음 → 선명도. 해당 조건이 없으면 rules=[]이며 기본값만 반환한다.
감마 계약: out=255×(in/255)^gamma. A가 역수 감마식을 쓰는 경우 어댑터에서 변환해야 한다.
실제 연산 순서(A-07 명세, 이슈 #44): 노이즈 제거 → Y 감마 → Y 히스토그램 평활화 → unsharp.
이전 문서의 평활화 → 감마는 제안이었으며, 구현은 원래 명세 순서를 따른다.
A 실행기의 Gaussian sigma=1.0, Unsharp sigma=1.0·threshold=5.0은 미튜닝 연동 기본값이다.
현재 파라미터 형식과 결정 근거는 [DIP 파라미터 가이드](dip_parameters.ko.md#7-apply_ops-파라미터-계약-v01-이슈-44)를 참조한다.
히스토그램 평활화는 밝기를 크게 바꿀 수 있으므로 실제 데이터로 검증해야 한다.
민감도 실험은 7개 임계값을 동시에 0.8/1.0/1.2배로 변경한다. gamma/unsharp 강도는 변경하지 않는다.
