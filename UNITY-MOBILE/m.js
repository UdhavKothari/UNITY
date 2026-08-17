/* REL-UNITY mobile — floor PWA. Same-origin /api + cookie auth as the web app. */
const ICON = {"grid_view":"<path d=\"M180-510q-24.75 0-42.37-17.63Q120-545.25 120-570v-210q0-24.75 17.63-42.38Q155.25-840 180-840h210q24.75 0 42.38 17.62Q450-804.75 450-780v210q0 24.75-17.62 42.37Q414.75-510 390-510H180Zm0 390q-24.75 0-42.37-17.63Q120-155.25 120-180v-210q0-24.75 17.63-42.38Q155.25-450 180-450h210q24.75 0 42.38 17.62Q450-414.75 450-390v210q0 24.75-17.62 42.37Q414.75-120 390-120H180Zm390-390q-24.75 0-42.37-17.63Q510-545.25 510-570v-210q0-24.75 17.63-42.38Q545.25-840 570-840h210q24.75 0 42.38 17.62Q840-804.75 840-780v210q0 24.75-17.62 42.37Q804.75-510 780-510H570Zm0 390q-24.75 0-42.37-17.63Q510-155.25 510-180v-210q0-24.75 17.63-42.38Q545.25-450 570-450h210q24.75 0 42.38 17.62Q840-414.75 840-390v210q0 24.75-17.62 42.37Q804.75-120 780-120H570ZM180-570h210v-210H180v210Zm390 0h210v-210H570v210Zm0 390h210v-210H570v210Zm-390 0h210v-210H180v210Zm390-390Zm0 180Zm-180 0Zm0-180Z\"/>","precision_manufacturing":"<path d=\"M213-120q-20 0-33.5-13.5T166-167q0-20 13.5-33.5T213-214h80L187-576q-32-15-50-40.5T119-684q0-47 34.5-81.5T235-800q44 0 73 23.5t39 62.5h146v-59q0-12 9-21t21-9q11 0 18.5 8.5T549-775l75-72q8-8 20.5-10.5T670-854l158 76q9 5 12.5 14t-1.5 19q-5 10-14.5 12t-18.5-3l-155-75-98 99v52l98 103 155-76q10-5 19-2.5t14 12.5q5 10 1.5 20T827-588l-153 72q-14 7-27 6.5T624-520l-75-72q0 14-7.5 21t-18.5 7q-12 0-21-9t-9-21v-60H345q0 12-6.5 24.5T323-609l205 395h111q20 0 33.5 13.5T686-167q0 20-13.5 33.5T639-120H213Zm62-524q16-16 16-40t-16-40q-16-16-40-16t-40 16q-16 16-16 40t16 40q16 16 40 16t40-16Zm84 430h102L272-581q-3 2-10 4t-11 3l108 360Zm102 0Z\"/>","notifications":"<path d=\"M190-200q-12.75 0-21.37-8.68-8.63-8.67-8.63-21.5 0-12.82 8.63-21.32 8.62-8.5 21.37-8.5h50v-304q0-84 49.5-150.5T420-798v-22q0-25 17.5-42.5T480-880q25 0 42.5 17.5T540-820v22q81 17 130.5 83.5T720-564v304h50q12.75 0 21.38 8.68 8.62 8.67 8.62 21.5 0 12.82-8.62 21.32-8.63 8.5-21.38 8.5H190Zm290-302Zm0 422q-33 0-56.5-23.5T400-160h160q0 33-23.5 56.5T480-80ZM300-260h360v-304q0-75-52.5-127.5T480-744q-75 0-127.5 52.5T300-564v304Z\"/>","person":"<path d=\"M372-523q-42-42-42-108t42-108q42-42 108-42t108 42q42 42 42 108t-42 108q-42 42-108 42t-108-42ZM160-220v-34q0-38 19-65t49-41q67-30 128.5-45T480-420q62 0 123 15.5T731-360q31 14 50 41t19 65v34q0 25-17.5 42.5T740-160H220q-25 0-42.5-17.5T160-220Zm60 0h520v-34q0-16-9.5-30.5T707-306q-64-31-117-42.5T480-360q-57 0-111 11.5T252-306q-14 7-23 21.5t-9 30.5v34Zm324.5-346.5Q570-592 570-631t-25.5-64.5Q519-721 480-721t-64.5 25.5Q390-670 390-631t25.5 64.5Q441-541 480-541t64.5-25.5ZM480-631Zm0 411Z\"/>","water_drop":"<path d=\"M251.5-174Q160-268 160-408q0-64 29-127t72.5-121q43.5-58 94-108.5T450-854q7-6 14.5-8.5T480-865q8 0 15.5 2.5T510-854q44 39 94.5 89.5t94 108.5Q742-598 771-535t29 127q0 140-91.5 234T480-80q-137 0-228.5-94ZM666-216.5Q740-293 740-408q0-79-66.5-179.5T480-800Q353-688 286.5-587.5T220-408q0 115 74 191.5T480-140q112 0 186-76.5ZM480-480Zm-1 272q16 0 24.5-5.5T512-230q0-11-8.5-17t-25.5-6q-42 0-85.5-26.5T337-373q-2-9-9-14.5t-15-5.5q-11 0-17 8.5t-4 17.5q15 84 71 121.5T479-208Z\"/>","waves":"<path d=\"M275-226q-53 0-83.5 31T110-151q-12 3-21-4.5T80-176q0-13 8.5-23t21.5-15q39-16 70.5-44t94.5-28q37 0 63 12.5t47.5 27.5q21.5 15 43.5 27.5t51 12.5q29 0 51-12.5t43.5-27.5q21.5-15 47.5-27.5t63-12.5q63 0 93.5 28t70.5 44q13 5 22 14.5t9 23.5q0 13-9.5 20.5T849-151q-51-13-81-44t-83-31q-30 0-52.5 12.5t-44 27.5q-21.5 15-47 27.5T480-146q-36 0-61.5-12.5t-47-27.5q-21.5-15-44-27.5T275-226Zm0-176q-53 0-83.5 31T110-327q-12 3-21-4.5T80-352q0-13 8.5-23t21.5-15q39-16 70.5-44t94.5-28q37 0 63 12.5t47.5 27.5q21.5 15 43.5 27.5t51 12.5q29 0 51-12.5t43.5-27.5q21.5-15 47.5-27.5t63-12.5q63 0 93.5 28t70.5 44q13 5 22 14.5t9 23.5q0 12-10 19.5t-21 4.5q-51-15-81-44.5T685-402q-30 0-52 12.5T589-362q-22 15-47.5 27.5T480-322q-36 0-61.5-12.5t-47-27.5q-21.5-15-44-27.5T275-402Zm0-176q-53 0-83.5 31T110-503q-12 3-21-4.5T80-528q0-13 9-22t21-14q39-14 70.5-44t94.5-30q37 0 63 12.5t47.5 27.5q21.5 15 43.5 27.5t51 12.5q29 0 51-12.5t43.5-27.5q21.5-15 47.5-27.5t63-12.5q63 0 93.5 30t70.5 44q13 5 22 14t9 22q0 13-9.5 20.5T849-503q-51-13-81-44t-83-31q-30 0-52.5 12.5t-44 27.5q-21.5 15-47 27.5T480-498q-36 0-61.5-12.5t-47-27.5q-21.5-15-44-27.5T275-578Zm0-176q-53 0-83.5 31T110-679q-12 3-21-4.5T80-704q0-13 8.5-23t21.5-15q39-16 70.5-44t94.5-28q37 0 63 12.5t47.5 27.5q21.5 15 43.5 27.5t51 12.5q29 0 51-12.5t43.5-27.5q21.5-15 47.5-27.5t63-12.5q63 0 93.5 28t70.5 44q13 5 22 14.5t9 23.5q0 13-9.5 20.5T849-679q-51-13-81-44t-83-31q-30 0-52.5 12.5t-44 27.5q-21.5 15-47 27.5T480-674q-36 0-61.5-12.5t-47-27.5q-21.5-15-44-27.5T275-754Z\"/>","compress":"<path d=\"M195-410q-14 0-24.5-10.5T160-445q0-14 10.5-24.5T195-480h570q14 0 24.5 10.5T800-445q0 14-10.5 24.5T765-410H195Zm-5-121q-13 0-21.5-8.5T160-561q0-13 8.5-21.5T190-591h580q13 0 21.5 8.5T800-561q0 13-8.5 21.5T770-531H190ZM457.5-88.5Q449-97 449-110v-128l-56 55q-9 8-21 8.5t-21-8.5q-9-9-9-21t9-21l107-106q5-5 10-7t11-2q6 0 11 2t10 7l105 106q8 9 8.5 21t-8.5 21q-9 9-21 9t-21-9l-54-55v128q0 13-8.5 21.5T479-80q-13 0-21.5-8.5ZM468-662q-5-2-10-7L352-775q-8-8-8.5-20.5T352-817q9-9 21-9t21 9l54 55v-128q0-13 8.5-21.5T478-920q13 0 21.5 8.5T508-890v128l56-55q9-8 21-8.5t21 8.5q9 9 9 21t-9 21L500-669q-5 5-10 7t-11 2q-6 0-11-2Z\"/>","local_fire_department":"<path d=\"M253-173q-93-93-93-227 0-116 71.5-225T428-811q17-11 34.5-.5T480-780v72q0 34 23.5 57t57.5 23q18 0 33.5-7.5T622-658q8-9 18-12.5t19 2.5q66 45 103.5 116T800-400q0 134-93 227T480-80q-134 0-227-93Zm-33-227q0 63 28.5 118.5T328-189q-4-12-6-24.5t-2-24.5q0-32 12-60t35-51l113-111 113 111q23 23 35 51t12 60q0 12-2 24.5t-6 24.5q51-37 79.5-92.5T740-400q0-54-23-105.5T651-600q-21 15-44 23.5t-46 8.5q-61 0-101-41.5T420-714v-20q-92 66-146 156.5T220-400Zm260 24-71 70q-14 14-21.5 31t-7.5 37q0 41 29 69.5t71 28.5q42 0 71-28.5t29-69.5q0-20-7.5-37T551-306l-71-70Z\"/>","cyclone":"<path d=\"M480-330q-62 0-106-44t-44-106q0-63 44-106.5T480-630q63 0 106.5 43.5T630-480q0 62-43.5 106T480-330Zm0-60q38 0 64-26.5t26-63.5q0-38-26-64t-64-26q-37 0-63.5 26T390-480q0 37 26.5 63.5T480-390Zm0 232q-119 0-211.5-15T114-205q-14-4-24-15t-10-26q0-12 10.5-19t23.5-3q48 14 91.5 22.5T271-233q-55-45-84-113.5T158-480q0-119 15-211.5T205-846q4-14 15-24t26-10q12 0 19 10.5t3 23.5q-14 48-22 90.5T235-691q48-55 114-83t131-28q119 0 211.5 15T846-755q14 4 24 15t10 26q0 12-10.5 19t-23.5 3q-48-14-90.5-22.5T691-726q57 49 84 115t27 131q0 119-15 211.5T755-114q-4 14-15 24t-26 10q-12 0-19.5-10.5T691-114q14-48 22.5-90.5T726-269q-51 58-116 84.5T480-158Zm185.5-136.5Q742-371 742-480t-76.5-185.5Q589-742 480-742t-185.5 76.5Q218-589 218-480t76.5 185.5Q371-218 480-218t185.5-76.5Z\"/>","mode_fan":"<path d=\"M424-80q-51 0-77.5-30.5T320-180q0-26 11.5-50.5T367-271q22-14 36.5-37.5T425-373q-1 0-1-.5t-2-1.5l-116 41q-17 6-33 10t-33 4q-63 0-111.5-55T80-536q0-51 30.5-77.5T179-640q26 0 51 11.5t41 35.5q14 22 39.5 37.5T373-535q.67-1 1.33-2 .67-1 .67-2l-41-115q-6-17-10-33t-4-32q0-64 55-112.5T536-880q51 0 77.5 30.5T640-781q0 26-11.5 51T593-689q-26 17-40.5 45T536-586q1 1 1.5.5t1.5 1.5l115-43q17-6 32.5-9.5T719-640q81 0 121 67t40 149q0 51-32 77.5T777-320q-25 0-48.5-11.5T689-367q-14-22-37.5-36.5T587-426q-1 2-1.6 3.06-.6 1.06-1.4 1.94l42 115q6 16 10 30.5t4 30.5q1 65-54 115T424-80Zm56-340q25 0 42.5-17.5T540-480q0-25-17.5-42.5T480-540q-25 0-42.5 17.5T420-480q0 25 17.5 42.5T480-420Zm-58-165q12-5 26-9t28-6q8-45 29.5-81t54.5-58q10-7 15-17.5t5-24.5q0-16.42-10.5-27.71T536-820q-43 0-98.5 20.55-55.5 20.54-57.5 80.32 0 11.21 2.5 21.17T388-680l34 95ZM240-380q14 0 40-8l95-34q-8-14-11.5-28t-3.5-26q-45-8-81-29.5T221-560q-7-10-19-15t-23-5q-19 0-29 10.5T140-536q0 61.94 25.63 108.97Q191.25-380 240-380Zm184 240q53.13 0 104.57-23Q580-186 580-242q0-11-2-19t-6-19l-34-95q-13 6-26.5 10t-27.5 5q-8 45-29.5 81T400-221q-9 6-14.5 18.5T380-179q1 15 11 27t33 12Zm353-240q16.83 0 29.91-9.17Q820-398.33 820-424q0-44-20.5-99t-81.33-57q-11.17 0-20.67 2-9.5 2-17.5 5l-95 35q5 8 10 25.5t5 28.5q45 8 81 29.5t58 54.5q6 8 16.67 14 10.66 6 21.33 6ZM600-484ZM476-600ZM360-476Zm124 116Z\"/>","timeline":"<path d=\"M109.91-240Q81-240 60.5-260.59 40-281.18 40-310.09t20.49-49.41q20.5-20.5 49.28-20.5 5.23 0 10.23.5t13 2.5l200-200q-2-8-2.5-13t-.5-10.23q0-28.78 20.59-49.28Q371.18-670 400.09-670t49.41 20.63q20.5 20.64 20.5 49.61 0 1.76-3 22.76l110 110q8-2 13-2.5t10-.5q5 0 10 .5t13 2.5l160-160q-2-8-2.5-13t-.5-10.23q0-28.78 20.59-49.28Q821.18-720 850.09-720t49.41 20.59q20.5 20.59 20.5 49.5t-20.49 49.41q-20.5 20.5-49.28 20.5-5.23 0-10.23-.5t-13-2.5L667-423q2 8 2.5 13t.5 10.23q0 28.78-20.59 49.28Q628.82-330 599.91-330t-49.41-20.49q-20.5-20.5-20.5-49.28 0-5.23.5-10.23t2.5-13L423-533q-8 2-13 2.5t-10.25.5q-1.75 0-22.75-3L177-333q2 8 2.5 13t.5 10.23q0 28.78-20.59 49.28Q138.82-240 109.91-240Z\"/>","schedule":"<path d=\"M513-492v-171q0-13-8.5-21.5T483-693q-13 0-21.5 8.5T453-663v183q0 6 2 11t6 10l144 149q9 10 22.5 9.5T650-310q9-9 9-22t-9-22L513-492ZM480-80q-82 0-155-31.5t-127.5-86Q143-252 111.5-325T80-480q0-82 31.5-155t86-127.5Q252-817 325-848.5T480-880q82 0 155 31.5t127.5 86Q817-708 848.5-635T880-480q0 82-31.5 155t-86 127.5Q708-143 635-111.5T480-80Zm0-400Zm0 340q140 0 240-100t100-240q0-140-100-240T480-820q-140 0-240 100T140-480q0 140 100 240t240 100Z\"/>","layers":"<path d=\"M151-386q-12-8.94-11.5-23.47T152.08-433q8.3-6 18.11-6 9.81 0 17.81 6l292 227 292-227q8.32-6 18.16-6t18.09 5.97q12 8.95 12.38 23.49Q821-395 809-386L517-159q-16.5 13-36.75 13T443-159L151-386Zm292 75L181-515q-23-17.88-23-46.94T181-609l262-204q16.5-13 36.75-13T517-813l262 204q23 17.88 23 46.94T779-515L517-311q-16.5 13-36.75 13T443-311Zm37-47 262-204-262-204-262 204 262 204Zm0-204Z\"/>","bolt":"<path d=\"m393-165 279-335H492l36-286-253 366h154l-36 255Zm-33-195H217q-18 0-26.5-16t2.5-31l338-488q8-11 20-15t24 1q12 5 19 16t5 24l-39 309h176q19 0 27 17t-4 32L388-66q-8 10-20.5 13T344-55q-11-5-17.5-16T322-95l38-265Zm113-115Z\"/>","qr_code_scanner":"<path d=\"M109.82-707Q97-707 88.5-715.63 80-724.25 80-737v-113q0-12.75 8.63-21.38Q97.25-880 110-880h113q12.75 0 21.38 8.68 8.62 8.67 8.62 21.5 0 12.82-8.62 21.32-8.63 8.5-21.38 8.5h-83v83q0 12.75-8.68 21.37-8.67 8.63-21.5 8.63ZM110-80q-12.75 0-21.37-8.63Q80-97.25 80-110v-113q0-12.75 8.68-21.38 8.67-8.62 21.5-8.62 12.82 0 21.32 8.62 8.5 8.63 8.5 21.38v83h83q12.75 0 21.38 8.68 8.62 8.67 8.62 21.5 0 12.82-8.62 21.32Q235.75-80 223-80H110Zm627 0q-12.75 0-21.37-8.68-8.63-8.67-8.63-21.5 0-12.82 8.63-21.32 8.62-8.5 21.37-8.5h83v-83q0-12.75 8.68-21.38 8.67-8.62 21.5-8.62 12.82 0 21.32 8.62 8.5 8.63 8.5 21.38v113q0 12.75-8.62 21.37Q862.75-80 850-80H737Zm91.5-635.63Q820-724.25 820-737v-83h-83q-12.75 0-21.37-8.68-8.63-8.67-8.63-21.5 0-12.82 8.63-21.32 8.62-8.5 21.37-8.5h113q12.75 0 21.38 8.62Q880-862.75 880-850v113q0 12.75-8.68 21.37-8.67 8.63-21.5 8.63-12.82 0-21.32-8.63ZM708-188v-63h63v63h-63Zm0-126v-63h63v63h-63Zm-63 63v-63h63v63h-63Zm-63 63v-63h63v63h-63Zm-63-63v-63h63v63h-63Zm126-126v-63h63v63h-63Zm-63 63v-63h63v63h-63Zm-63-63v-63h63v63h-63Zm30-143q-12.75 0-21.37-8.63Q519-537.25 519-550v-192q0-12.75 8.63-21.38Q536.25-772 549-772h192q12.75 0 21.38 8.62Q771-754.75 771-742v192q0 12.75-8.62 21.37Q753.75-520 741-520H549ZM218-188q-12.75 0-21.37-8.63Q188-205.25 188-218v-192q0-12.75 8.63-21.38Q205.25-440 218-440h192q12.75 0 21.38 8.62Q440-422.75 440-410v192q0 12.75-8.62 21.37Q422.75-188 410-188H218Zm0-332q-12.75 0-21.37-8.63Q188-537.25 188-550v-192q0-12.75 8.63-21.38Q205.25-772 218-772h192q12.75 0 21.38 8.62Q440-754.75 440-742v192q0 12.75-8.62 21.37Q422.75-520 410-520H218Zm20 282h152v-152H238v152Zm0-332h152v-152H238v152Zm331 0h152v-152H569v152Z\"/>","play_arrow":"<path d=\"M320-258v-450q0-14 9-22t21-8q4 0 8 1t8 3l354 226q7 5 10.5 11t3.5 14q0 8-3.5 14T720-458L366-232q-4 2-8 3t-8 1q-12 0-21-8t-9-22Zm60-225Zm0 171 269-171-269-171v342Z\"/>","check":"<path d=\"m378-332 363-363q9-9 21.5-9t21.5 9q9 9 9 21.5t-9 21.5L399-267q-9 9-21 9t-21-9L175-449q-9-9-8.5-21.5T176-492q9-9 21.5-9t21.5 9l159 160Z\"/>","check_circle":"<path d=\"m421-389-98-98q-9-9-22-9t-23 10q-9 9-9 22t9 22l122 123q9 9 21 9t21-9l239-239q10-10 10-23t-10-23q-10-9-23.5-8.5T635-603L421-389Zm59 309q-82 0-155-31.5t-127.5-86Q143-252 111.5-325T80-480q0-83 31.5-156t86-127Q252-817 325-848.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 82-31.5 155T763-197.5q-54 54.5-127 86T480-80Zm0-60q142 0 241-99.5T820-480q0-142-99-241t-241-99q-141 0-240.5 99T140-480q0 141 99.5 240.5T480-140Zm0-340Z\"/>","arrow_back":"<path d=\"m274-450 227 227q9 9 9 21t-9 21q-9 9-21 9t-21-9L181-459q-5-5-7-10t-2-11q0-6 2-11t7-10l278-278q9-9 21-9t21 9q9 9 9 21t-9 21L274-510h496q13 0 21.5 8.5T800-480q0 13-8.5 21.5T770-450H274Z\"/>","refresh":"<path d=\"M480-160q-133 0-226.5-93.5T160-480q0-133 93.5-226.5T480-800q85 0 149 34.5T740-671v-99q0-13 8.5-21.5T770-800q13 0 21.5 8.5T800-770v194q0 13-8.5 21.5T770-546H576q-13 0-21.5-8.5T546-576q0-13 8.5-21.5T576-606h138q-38-60-97-97t-137-37q-109 0-184.5 75.5T220-480q0 109 75.5 184.5T480-220q75 0 140-39.5T717-366q5-11 16.5-16.5t22.5-.5q12 5 16 16.5t-1 23.5q-39 84-117.5 133.5T480-160Z\"/>","logout":"<path d=\"M180-120q-24 0-42-18t-18-42v-600q0-24 18-42t42-18h269q12.75 0 21.38 8.68 8.62 8.67 8.62 21.5 0 12.82-8.62 21.32-8.63 8.5-21.38 8.5H180v600h269q12.75 0 21.38 8.68 8.62 8.67 8.62 21.5 0 12.82-8.62 21.32-8.63 8.5-21.38 8.5H180Zm545-330H390q-12.75 0-21.37-8.68-8.63-8.67-8.63-21.5 0-12.82 8.63-21.32 8.62-8.5 21.37-8.5h333l-81-81q-9-9-8.5-21t9.5-21q9-9 21.5-9t21.5 9l133 133q9 9 9 21t-9 21L687-326q-8.8 9-20.9 8.5-12.1-.5-21.49-9.5-8.61-9-8.61-21.5t9-21.5l80-80Z\"/>","chevron_right":"<path d=\"M530-481 353-658q-9-9-8.5-21t9.5-21q9-9 21.5-9t21.5 9l198 198q5 5 7 10t2 11q0 6-2 11t-7 10L396-261q-9 9-21 8.5t-21-9.5q-9-9-9-21.5t9-21.5l176-176Z\"/>","inventory_2":"<path d=\"M180-80q-24.75 0-42.37-17.63Q120-115.25 120-140v-483q-17-6-28.5-21.39T80-680v-140q0-24.75 17.63-42.38Q115.25-880 140-880h680q24.75 0 42.38 17.62Q880-844.75 880-820v140q0 20.22-11.5 35.61T840-623v483q0 24.75-17.62 42.37Q804.75-80 780-80H180Zm0-540v480h600v-480H180Zm-40-60h680v-140H140v140Zm250 260h180q12.75 0 21.38-8.68 8.62-8.67 8.62-21.5 0-12.82-8.62-21.32-8.63-8.5-21.38-8.5H390q-12.75 0-21.37 8.68-8.63 8.67-8.63 21.5 0 12.82 8.63 21.32 8.62 8.5 21.37 8.5Zm90 40Z\"/>","verified":"<path d=\"m437-433-73-76q-9-10-22-10t-23 9q-10 10-10 23t10 23l97 96q9 9 21 9t21-9l183-182q9-9 9-22t-10-22q-9-8-21.5-7.5T598-593L437-433ZM332-84l-62-106-124-25q-11-2-18.5-12t-5.5-21l14-120-79-92q-8-8-8-20t8-20l79-91-14-120q-2-11 5.5-21t18.5-12l124-25 62-107q6-10 17-14t22 1l109 51 109-51q11-5 22-1.5t17 13.5l63 108 123 25q11 2 18.5 12t5.5 21l-14 120 79 91q8 8 8 20t-8 20l-79 92 14 120q2 11-5.5 21T814-215l-123 25-63 107q-6 10-17 13.5T589-71l-109-51-109 51q-11 5-22 1t-17-14Zm41-55 107-45 110 45 67-100 117-30-12-119 81-92-81-94 12-119-117-28-69-100-108 45-110-45-67 100-117 28 12 119-81 94 81 92-12 121 117 28 70 100Zm107-341Z\"/>","wifi_off":"<path d=\"M784-91 411-463q-42 10-78 29.5T267-389q-15 12-33.5 13.5T201-388q-14-14-13-32.5t15-31.5q29-26 62-46t75-37L229-646q-35 18-68.5 40.5T98-558q-15 13-34 13.5T31-558q-14-14-12.5-32.5T34-622q30-27 62-50t65-41l-71-71q-9-9-9-21.5t9-21.5q9-9 21.5-9t21.5 9l694 694q9 9 9 21t-9 21q-9 9-21.5 9T784-91Zm-367-63q-27-27-27-63t27-63q27-27 63-27t63 27q27 27 27 63t-27 63q-27 27-63 27t-63-27Zm343-235q-14 14-33 14t-34-13q-32-27-71.5-57T549-500l-12-9q-15-11-7-29t28-14q57 11 104.5 35.5T754-454q15 13 17.5 32T760-389Zm169-169q-14 14-33.5 13.5T861-558q-83-70-178-111t-203-41q-37 0-71 4.5T352-693q-18 6-34.5-2.5T295-722q-6-18 2.5-35.5T324-780q36-11 75.5-15.5T480-800q128 0 241.5 48.5T926-622q14 13 15.5 31.5T929-558Z\"/>","warning":"<path d=\"M92-120q-9 0-15.5-4T66-135q-4-7-4.5-14.5T66-165l388-670q5-8 11.5-11.5T480-850q8 0 14.5 3.5T506-835l388 670q5 8 4.5 15.5T894-135q-4 7-10.5 11t-15.5 4H92Zm52-60h672L480-760 144-180Zm361.5-65.5Q514-254 514-267t-8.5-21.5Q497-297 484-297t-21.5 8.5Q454-280 454-267t8.5 21.5Q471-237 484-237t21.5-8.5Zm0-111Q514-365 514-378v-164q0-13-8.5-21.5T484-572q-13 0-21.5 8.5T454-542v164q0 13 8.5 21.5T484-348q13 0 21.5-8.5ZM480-470Z\"/>","science":"<path d=\"M172-120q-41.78 0-59.39-39T124-230l248-280v-270h-52q-12.75 0-21.37-8.68-8.63-8.67-8.63-21.5 0-12.82 8.63-21.32 8.62-8.5 21.37-8.5h320q12.75 0 21.38 8.68 8.62 8.67 8.62 21.5 0 12.82-8.62 21.32-8.63 8.5-21.38 8.5h-52v270l248 280q29 32 11.39 71T788-120H172Zm-12-60h640L528-488v-292h-96v292L160-180Zm318-300Z\"/>","cleaning_services":"<path d=\"M180-40q-24.75 0-42.37-17.63Q120-75.25 120-100v-230q0-78.85 55.57-134.42Q231.15-520 310-520h60v-340q0-24.75 17.63-42.38Q405.25-920 430-920h100q24.75 0 42.38 17.62Q590-884.75 590-860v340h60q78.85 0 134.42 55.58Q840-408.85 840-330v230q0 24.75-17.62 42.37Q804.75-40 780-40H180Zm0-60h105v-130q0-12.75 8.68-21.38 8.67-8.62 21.5-8.62 12.82 0 21.32 8.62 8.5 8.63 8.5 21.38v130h105v-130q0-12.75 8.68-21.38 8.67-8.62 21.5-8.62 12.82 0 21.32 8.62 8.5 8.63 8.5 21.38v130h105v-130q0-12.75 8.68-21.38 8.67-8.62 21.5-8.62 12.82 0 21.32 8.62 8.5 8.63 8.5 21.38v130h105v-230q0-54.17-37.92-92.08Q704.17-460 650-460H310q-54.17 0-92.08 37.92Q180-384.17 180-330v230Zm350-420v-340H430v340h100Zm0 0H430h100Z\"/>","add":"<path d=\"M450-450H230q-12.75 0-21.37-8.68-8.63-8.67-8.63-21.5 0-12.82 8.63-21.32 8.62-8.5 21.37-8.5h220v-220q0-12.75 8.68-21.38 8.67-8.62 21.5-8.62 12.82 0 21.32 8.62 8.5 8.63 8.5 21.38v220h220q12.75 0 21.38 8.68 8.62 8.67 8.62 21.5 0 12.82-8.62 21.32-8.63 8.5-21.38 8.5H510v220q0 12.75-8.68 21.37-8.67 8.63-21.5 8.63-12.82 0-21.32-8.63-8.5-8.62-8.5-21.37v-220Z\"/>","priority_high":"<path d=\"M479.91-120q-28.91 0-49.41-20.59-20.5-20.59-20.5-49.5t20.59-49.41q20.59-20.5 49.5-20.5t49.41 20.59q20.5 20.59 20.5 49.5t-20.59 49.41q-20.59 20.5-49.5 20.5Zm0-240q-28.91 0-49.41-20.56Q410-401.13 410-430v-340q0-28.88 20.59-49.44t49.5-20.56q28.91 0 49.41 20.56Q550-798.88 550-770v340q0 28.87-20.59 49.44Q508.82-360 479.91-360Z\"/>","sync":"<path d=\"M220-477q0 63 23.5 109.5T307-287l30 21v-94q0-13 8.5-21.5T367-390q13 0 21.5 8.5T397-360v170q0 13-8.5 21.5T367-160H197q-13 0-21.5-8.5T167-190q0-13 8.5-21.5T197-220h100l-15-12q-64-51-93-111t-29-134q0-94 49.5-171.5T342-766q11-5 21 0t14 16q5 11 0 22.5T361-710q-64 34-102.5 96.5T220-477Zm520-6q0-48-23.5-97.5T655-668l-29-26v94q0 13-8.5 21.5T596-570q-13 0-21.5-8.5T566-600v-170q0-13 8.5-21.5T596-800h170q13 0 21.5 8.5T796-770q0 13-8.5 21.5T766-740H665l15 14q60 56 90 120t30 123q0 93-48 169.5T623-195q-11 6-22.5 1.5T584-210q-5-11 0-22.5t16-17.5q65-33 102.5-96T740-483Z\"/>","stop_circle":"<path d=\"M360-330h240q12.75 0 21.38-8.63Q630-347.25 630-360v-240q0-12.75-8.62-21.38Q612.75-630 600-630H360q-12.75 0-21.37 8.62Q330-612.75 330-600v240q0 12.75 8.63 21.37Q347.25-330 360-330ZM480.27-80q-82.74 0-155.5-31.5Q252-143 197.5-197.5t-86-127.34Q80-397.68 80-480.5t31.5-155.66Q143-709 197.5-763t127.34-85.5Q397.68-880 480.5-880t155.66 31.5Q709-817 763-763t85.5 127Q880-563 880-480.27q0 82.74-31.5 155.5Q817-252 763-197.68q-54 54.31-127 86Q563-80 480.27-80Zm.23-60Q622-140 721-239.5t99-241Q820-622 721.19-721T480-820q-141 0-240.5 98.81T140-480q0 141 99.5 240.5t241 99.5Zm-.5-340Z\"/>","calendar_view_week":"<path d=\"M140-160q-24 0-42-18t-18-42v-520q0-24 18-42t42-18h680q24 0 42 18t18 42v520q0 24-18 42t-42 18H140Zm374-60h123v-520H514v520Zm-190 0h123v-520H324v520Zm-184 0h124v-520H140v520Zm557 0h123v-520H697v520Z\"/>","done_all":"<path d=\"M91-445q-9-9-8.5-21.5T92-488q9-9 21.5-9t21.5 9l159 160 11 11 11 11q9 9 9 21t-9 21l-1 1q-9 9-21 9t-21-9L91-445Zm373 117 363-363q9-9 21.5-9t21.5 9q9 9 9 21.5t-9 21.5L485-263q-9 9-21 9t-21-9L261-445q-9-9-8.5-21.5T262-488q9-9 21.5-9t21.5 9l159 160Zm236-320L485-433q-9 9-21 8.5t-21-9.5q-9-9-9-21.5t9-21.5l214-214q9-9 21.5-9t21.5 9q9 9 9 21.5t-9 21.5Z\"/>","hourglass_top":"<path d=\"M308-140h344v-127q0-72-50-121.5T480-438q-72 0-122 49.5T308-267v127ZM190-80q-13 0-21.5-8.5T160-110q0-13 8.5-21.5T190-140h58v-127q0-71 40-129t106-84q-66-27-106-85t-40-129v-126h-58q-13 0-21.5-8.5T160-850q0-13 8.5-21.5T190-880h580q13 0 21.5 8.5T800-850q0 13-8.5 21.5T770-820h-58v126q0 71-40 129t-106 85q66 26 106 84t40 129v127h58q13 0 21.5 8.5T800-110q0 13-8.5 21.5T770-80H190Z\"/>","event_available":"<path d=\"m433-313 163-163q9-9 21-8.5t21 9.5q9 9 9 21.2 0 12.19-9 20.8L454-249q-9 9-21 9t-21-9l-96-95q-9-8.61-9-20.8 0-12.2 9-21.2t21-8.5q12 .5 21 8.5l75 73ZM180-80q-24 0-42-18t-18-42v-620q0-24 18-42t42-18h65v-28q0-13.6 9-22.8 9-9.2 23.02-9.2t23.5 9.2Q310-861.6 310-848v28h340v-28q0-13.6 9-22.8 9-9.2 23.02-9.2t23.5 9.2Q715-861.6 715-848v28h65q24 0 42 18t18 42v620q0 24-18 42t-42 18H180Zm0-60h600v-430H180v430Zm0-490h600v-130H180v130Zm0 0v-130 130Z\"/>"};
const $ = id => document.getElementById(id);
const app = () => $("app");
function svg(n, px){ const g = ICON[n] || ""; return '<span class="ic"'+(px?' style="font-size:'+px+'px"':'')+'><svg viewBox="0 -960 960 960" aria-hidden="true">'+g+'</svg></span>'; }
function esc(s){ return String(s==null?"":s).replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
const MC_ICON = t => ({jet:"water_drop",jigger:"waves",drum:"cyclone",stentor:"compress",hydro:"mode_fan",rope:"timeline"}[t] || "precision_manufacturing");
function empty(icon, title, desc){   // teaching empty state: icon + what's going on + what fixes it
  return '<div class="empty">'+svg(icon)+'<b>'+esc(title)+'</b>'+(desc?'<span>'+esc(desc)+'</span>':'')+'</div>';
}

let USER = null, DB = null, OFFLINE = false, TOASTT = null;

/* ---- permissions (mirror the web app: role -> viewable pages + editable subset) ---- */
function can(p){ return !!USER && (USER.perms||[]).includes(p); }
function canEdit(p){ return !!USER && (USER.edit||[]).includes(p); }
function canBatch(){ return canEdit("batches") || canEdit("op_batch"); }   // may start/finish batches

function toast(m){ const t = $("toast"); t.textContent = m; t.classList.add("on"); clearTimeout(TOASTT); TOASTT = setTimeout(()=>t.classList.remove("on"), 2400); }
function pad(n){ return String(n).padStart(2,"0"); }
function nowStamp(){ const d = new Date(); return d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate())+" "+pad(d.getHours())+":"+pad(d.getMinutes()); }
function hm(dt){ return (dt && dt.length>=16) ? dt.slice(11,16) : ""; }
function elapsed(startedAt){
  if(!startedAt) return "";
  const s = new Date(startedAt.replace(" ","T")); if(isNaN(s)) return "";
  let mins = Math.max(0, Math.round((Date.now()-s.getTime())/60000));
  const h = Math.floor(mins/60); mins = mins%60;
  return (h?h+"h ":"")+mins+"m";
}

async function apiGet(path){
  const r = await fetch(path, {credentials:"same-origin"});
  if(r.status===401) return {__auth:false};
  return r.json();
}
async function apiPost(body){
  const r = await fetch("/api", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body), credentials:"same-origin"});
  return r.json();
}

/* ---------------- data helpers ---------------- */
function machineBatches(mid){
  return (DB.batches||[]).filter(b => b.machine===mid && b.status!=="done").slice().sort((a,b)=>(+a.seq||0)-(+b.seq||0));
}
function currentBatch(mid){ const r = machineBatches(mid); return r.find(b=>b.status==="running") || r[0] || null; }
function shadeColor(b){
  if(!b) return "var(--surface-3)";
  const rec = (DB.shadeRecipes||[]).find(s=>s.quality===b.quality && String(s.shade)===String(b.shadeNo));
  if(rec && rec.hex) return rec.hex;
  return "#9aa4b4";
}
function batchLots(b){ return (b.lots||[]).map(l=>l.lotId).filter(Boolean).join(", ") || (b.lotIds||[]).join(", ") || "—"; }
function statusPill(b){
  if(b.wash) return '<span class="pill wash">'+svg("cleaning_services",14)+'WASH</span>';
  if(b.status==="running") return '<span class="pill run">'+svg("bolt",14)+'RUNNING</span>';
  return '<span class="pill free">PLANNED</span>';
}

/* ---------------- shell ---------------- */
const TABS = [["/", "grid_view", "Floor", "op_floor"], ["/plan", "calendar_view_week", "Plan", "op_massplan"],
              ["/alerts", "notifications", "Alerts", null], ["/me", "person", "Me", null]];
function tabAllowed(t){ return !t[3] || can(t[3]); }               // null perm = always visible (Alerts, Me)
function allowedTabs(){ return TABS.filter(tabAllowed); }
function firstTab(){ const t = allowedTabs()[0]; return t ? t[0] : "/me"; }
const NEEDS = h => (h==="/"||h===""||h.startsWith("/machine/")) ? "op_floor" : (h==="/plan" ? "op_massplan" : null);
function shell(opts){
  const { title, body, tab, back, action } = opts;
  let ab = '<header class="appbar">';
  ab += back ? '<button class="ab-btn" onclick="location.hash=\''+back+'\'">'+svg("arrow_back")+'</button>' : '<span class="ab-btn" style="width:6px"></span>';
  ab += '<h1>'+esc(title)+'</h1>';
  ab += action || '<button class="ab-btn" onclick="refresh()">'+svg("refresh")+'</button>';
  ab += '</header>';
  const off = OFFLINE ? '<div class="offline-chip">'+svg("wifi_off")+'Offline — showing last synced</div>' : '';
  let tabs = '<nav class="tabs">';
  allowedTabs().forEach(([h,ic,lb]) => {
    const on = (tab===h) ? " on" : "";
    const dot = (h==="/alerts" && alertsCount()>0) ? '<span class="dot"></span>' : "";
    tabs += '<button class="tab'+on+'" onclick="location.hash=\''+h+'\'">'+dot+svg(ic)+'<span>'+lb+'</span></button>';
  });
  tabs += '</nav>';
  app().className = "app";
  app().innerHTML = ab + off + '<main class="main">'+body+'</main>' + tabs;
}

/* ---------------- views ---------------- */
function renderFloor(){
  const ms = DB.machines || [];
  let body;
  if(!ms.length){ body = empty("precision_manufacturing", "No machines yet", "Add machines in the Admin console and they'll show up here."); }
  else body = ms.slice().sort((a,b)=>String(a.id).localeCompare(String(b.id),undefined,{numeric:true})).map(machineCard).join("");
  shell({ title:"Shop floor", body, tab:"/" });
}
function machineCard(m){
  const cur = currentBatch(m.id), q = machineBatches(m.id), running = cur && cur.status==="running";
  const cap = +m.capMax || 0, kg = cur ? (+cur.weight||0) : 0;
  const pct = (running && cap) ? Math.max(6, Math.min(100, Math.round(kg/cap*100))) : 0;
  const col = running ? shadeColor(cur) : "";
  const pill = running ? '<span class="pill run">'+svg("bolt",14)+'RUNNING</span>'
             : (q.length ? '<span class="pill free">IDLE · '+q.length+' queued</span>' : '<span class="pill free">IDLE</span>');
  const vat = running
    ? '<div class="vat"><div class="fill" style="background:'+col+';transform:scaleY('+(pct/100)+')"></div><div class="pct">'+pct+'%</div></div>'
    : '<div class="vat idle"></div>';
  let info;
  if(cur){
    info = '<div class="mc-info"><div class="mc-shade"><span class="sw" style="background:'+shadeColor(cur)+'"></span>'+esc(cur.shadeNo||cur.quality||"—")+'</div>'
      + '<div class="mc-sub">lot <span class="lot">'+esc(batchLots(cur))+'</span> · '+esc(cur.quality||"")+'</div>'
      + '<div class="mc-glance">'+(running ? (elapsed(cur.startedAt) ? "running "+elapsed(cur.startedAt) : "running") : "next up") +'</div></div>';
  } else {
    info = '<div class="mc-info"><div class="mc-shade" style="color:var(--muted)">Idle</div><div class="mc-sub">No batch loaded</div></div>';
  }
  return '<div class="card mc tap" onclick="location.hash=\'/machine/'+encodeURIComponent(m.id)+'\'">'
    + '<div class="mc-h"><div class="mc-tile">'+svg(MC_ICON(m.type))+'</div>'
    + '<div><div class="mc-id">'+esc(m.id)+'</div><div class="mc-type">'+esc(m.type||"")+(cap?' · '+cap+' kg':'')+'</div></div>'
    + '<span style="margin-left:auto">'+pill+'</span></div>'
    + '<div class="mc-b">'+vat+info+'</div>'
    + '<div class="mc-f">'+svg("layers")+(q.length ? (q.length+' batch(es) planned') : 'nothing queued')+'<span class="chev" style="margin-left:auto">'+svg("chevron_right")+'</span></div></div>';
}

function renderMachine(id){
  const m = (DB.machines||[]).find(x=>x.id===id);
  if(!m){ shell({title:"Machine", body: empty("precision_manufacturing","Machine not found",""), tab:"/", back:"/"}); return; }
  const rows = machineBatches(id);
  let body = machineCard(m);
  body += '<div class="sec-label">Batches on '+esc(id)+'</div>';
  body += rows.length ? rows.map(batchRow).join("") : empty("done_all","All clear","No planned batches on this machine.");
  shell({ title:esc(id), body, tab:"/", back:"/" });
}
function batchRow(b){
  const sub = b.wash ? "Machine wash" : (esc(b.quality||"")+" · "+ (b.pcs||0) +" pcs · "+ (b.weight||0) +" kg");
  return '<div class="brow tap" onclick="openBatch(\''+esc(b.id)+'\')">'
    + '<span class="sw" style="background:'+shadeColor(b)+'"></span>'
    + '<div style="min-width:0"><div class="lot">'+esc(b.wash?"WASH":batchLots(b))+'</div><div class="q">'+sub+'</div></div>'
    + '<div class="r">'+statusPill(b)+(b.startedAt?'<span class="q tnum">in '+hm(b.startedAt)+'</span>':'')+'</div></div>';
}

function renderPlan(){
  const rows = (DB.batches||[]).filter(b=>b.status!=="done").slice()
    .sort((a,b)=>String(a.machine||"").localeCompare(String(b.machine||""),undefined,{numeric:true}) || (+a.seq||0)-(+b.seq||0));
  let body;
  if(!rows.length) body = empty("event_available", "Nothing planned", "Batches created in the Batch planner will appear here.");
  else {
    let cur = null, out = "";
    rows.forEach(b => { if(b.machine!==cur){ cur=b.machine; out += '<div class="sec-label">'+svg("precision_manufacturing",14)+' '+esc(cur||"Unassigned")+'</div>'; } out += batchRow(b); });
    body = out;
  }
  shell({ title:"Plan", body, tab:"/plan" });
}

function alertsCount(){ return (DB && DB.plcAlerts) ? DB.plcAlerts.filter(a=>!a.cleared).length : 0; }
function renderAlerts(){
  const al = ((DB && DB.plcAlerts) || []).filter(a=>!a.cleared).slice().reverse();   // newest first
  let body;
  if(!al.length){ body = empty("notifications", "No alerts", "Temperature drift and machine alarms from the PLC show up here. All clear right now."); }
  else body = al.map(a=>{
    const ic = a.kind==="temp" ? "local_fire_department" : "warning";
    return '<div class="brow"><span class="mc-tile" style="width:40px;height:40px;background:var(--danger-soft);color:var(--danger)">'+svg(ic,22)+'</span>'
      + '<div style="min-width:0;flex:1"><div class="lot">'+esc(a.machine||"")+'</div><div class="q">'+esc(a.message||"")+'</div></div>'
      + '<div class="r"><span class="q tnum">'+esc((a.ts||"").slice(11,16))+'</span></div></div>';
  }).join("");
  shell({ title:"Alerts", body, tab:"/alerts" });
}

function renderMe(){
  const perms = (USER.perms||[]).length;
  const body = '<div class="card" style="display:flex;align-items:center;gap:14px">'
    + '<div class="mc-tile" style="background:var(--primary);color:#fff">'+svg("person")+'</div>'
    + '<div><div class="mc-id" style="font-size:18px">'+esc(USER.username)+'</div><div class="mc-type">'+esc(USER.role||"")+' · '+perms+' pages</div></div></div>'
    + '<div class="me-row">'+svg(OFFLINE?"wifi_off":"sync")+'<div class="t"><b>'+(OFFLINE?"Offline":"Live")+'</b><span>'+(OFFLINE?"Showing last synced data":"Connected to the factory server")+'</span></div>'
    + '<button class="btn sm ghost" onclick="refresh()">'+svg("refresh")+'Sync</button></div>'
    + '<div class="sec-label">Your access</div>'
    + '<div class="card" style="display:flex;flex-direction:column;gap:8px">'
    +   TABS.filter(t=>t[3]).map(t=>'<div class="kv" style="padding:6px 2px"><span class="k">'+t[2]+'</span><span class="v">'+(can(t[3])?svg("check_circle",18)+' Yes':'<span style="color:var(--muted)">No</span>')+'</span></div>').join("")
    +   '<div class="kv" style="padding:6px 2px"><span class="k">Start / finish batches</span><span class="v">'+(canBatch()?svg("check_circle",18)+' Yes':'<span style="color:var(--muted)">No</span>')+'</span></div>'
    + '</div>'
    + '<button class="btn ghost" style="margin-top:4px" onclick="signOut()">'+svg("logout")+'Sign out</button>'
    + '<div class="empty" style="padding:22px 24px"><span style="font-size:12px">REL-UNITY floor app · v1 · add to home screen for full-screen use</span></div>';
  shell({ title:"Me", body, tab:"/me" });
}

/* ---------------- batch sheet + actions ---------------- */
let SHEET_B = null;
function openBatch(id){
  const b = (DB.batches||[]).find(x=>x.id===id); if(!b) return; SHEET_B = b;
  const running = b.status==="running";
  const kv = (k,v)=>'<div class="kv"><span class="k">'+k+'</span><span class="v">'+v+'</span></div>';
  let acts;
  if(!canBatch()){
    acts = '<div class="empty" style="padding:16px 8px 6px">'+svg("verified")+'<b>View only</b><span>Your role can’t start or finish batches.</span></div>';
  } else if(b.wash){
    acts = running ? '<button class="btn success" onclick="act(\'finish\')">'+svg("check")+'Wash done</button>'
                   : '<button class="btn accent" onclick="act(\'start\')">'+svg("play_arrow")+'Start wash</button>';
  } else {
    acts = running
      ? '<button class="btn success" onclick="act(\'finish\')">'+svg("check_circle")+'Finish batch</button>'
      : '<button class="btn accent" onclick="act(\'start\')">'+svg("play_arrow")+'Start batch</button>';
  }
  const html = '<div class="sheet" onclick="event.stopPropagation()"><div class="grab"></div>'
    + '<h2>'+svg(b.wash?"cleaning_services":"layers",22)+' '+esc(b.wash?"Machine wash":batchLots(b))+'</h2>'
    + '<div style="margin:2px 2px 10px">'+statusPill(b)+' <span class="pill free">'+esc(b.machine||"")+'</span></div>'
    + (b.wash?'':kv("Shade", '<span class="sw" style="display:inline-block;vertical-align:-3px;background:'+shadeColor(b)+'"></span> '+esc(b.shadeNo||"—")))
    + (b.wash?'':kv("Quality", esc(b.quality||"—")))
    + (b.wash?'':kv("Pcs · Mtr · Kg", '<span class="tnum">'+(b.pcs||0)+' · '+(b.mtr||0)+' · '+(b.weight||0)+'</span>'))
    + kv("In time", '<span class="tnum">'+(b.startedAt?esc(b.startedAt):"—")+'</span>')
    + kv("Out time", '<span class="tnum">'+(b.completedAt?esc(b.completedAt):"—")+'</span>')
    + '<div style="margin-top:16px">'+acts+'</div>'
    + '<button class="btn ghost sm" style="width:100%;margin-top:10px" onclick="closeSheet()">Close</button></div>';
  const sc = document.createElement("div"); sc.className = "scrim"; sc.id = "sheetScrim"; sc.innerHTML = html;
  sc.addEventListener("click", closeSheet); document.body.appendChild(sc);
  requestAnimationFrame(()=>sc.classList.add("on"));
}
function closeSheet(){ const sc = $("sheetScrim"); if(sc){ sc.classList.remove("on"); setTimeout(()=>sc.remove(), 240); } SHEET_B = null; }
async function act(kind){
  const b = SHEET_B; if(!b) return;
  // batchStatus is server-side permission-checked (batches/op_batch edit) and audit-logged with who+when
  const to = kind==="start" ? "running" : "done";
  const res = await apiPost({op:"batchStatus", id:b.id, to}).catch(()=>({error:"No connection"}));
  if(res && res.error){ toast(res.error); return; }
  const nb = res.row || Object.assign({}, b, {status:to});
  const i = (DB.batches||[]).findIndex(x=>x.id===b.id); if(i>=0) DB.batches[i] = nb;
  closeSheet(); route(); toast(kind==="start" ? "Batch started" : "Batch finished");
}

/* ---------------- login ---------------- */
function renderLogin(){
  app().className = "";
  app().innerHTML = '<form class="login" onsubmit="doLogin(event)">'
    + '<div class="brand"><img src="icon.svg" alt=""><b>REL-UNITY</b><span>Factory floor</span></div>'
    + '<div class="fld"><label>Username</label><input id="lu" autocomplete="username" autocapitalize="characters" required></div>'
    + '<div class="fld"><label>Password / PIN</label><input id="lp" type="password" inputmode="numeric" autocomplete="current-password" required></div>'
    + '<button class="btn primary" type="submit" id="lbtn">'+svg("check")+'Sign in</button>'
    + '<div class="empty" style="padding:14px"><span style="font-size:12px">On the factory Wi-Fi only</span></div></form>';
}
async function doLogin(e){
  e.preventDefault();
  const u = $("lu").value.trim(), p = $("lp").value;
  if(!u || !p) return;
  $("lbtn").disabled = true;
  const res = await apiPost({op:"login", username:u, password:p}).catch(()=>({error:"No connection"}));
  $("lbtn").disabled = false;
  if(res && res.error){ toast(res.error); return; }
  USER = res.user; await loadDB(); location.hash = "/"; route();
}
async function signOut(){ await apiPost({op:"logout"}).catch(()=>{}); USER = null; DB = null; renderLogin(); }

/* ---------------- boot ---------------- */
async function loadDB(){
  try{ const d = await apiGet("/api/db"); if(d && d.error) throw new Error(d.error); if(d && d.__auth===false){ return renderLogin(); } DB = d; OFFLINE = false; }
  catch(err){ OFFLINE = true; if(!DB) DB = {machines:[],batches:[],lots:[],qualities:[],shadeRecipes:[]}; }
}
async function refresh(){ await loadDB(); route(); toast(OFFLINE ? "Offline — couldn't sync" : "Synced"); }
function route(){
  if(!USER){ return renderLogin(); }
  const h = (location.hash.slice(1) || "/");
  const needs = NEEDS(h);
  if(needs && !can(needs)){                 // this role can't see this page -> bounce to one it can
    const ft = firstTab();
    if(ft !== h && !((ft==="/"||ft==="") && (h==="/"||h===""))){ location.hash = ft; return; }
    return renderNoAccess();
  }
  if(h.startsWith("/machine/")) return renderMachine(decodeURIComponent(h.split("/")[2]||""));
  if(h==="/plan") return renderPlan();
  if(h==="/alerts") return renderAlerts();
  if(h==="/me") return renderMe();
  return renderFloor();
}
function renderNoAccess(){
  shell({ title:"REL-UNITY", tab:"/me",
    body: empty("person", "No floor access yet", "Your account doesn't have access to the floor or plan. Ask an admin to grant your role the pages you need in the web console.") });
}
window.addEventListener("hashchange", route);
async function boot(){
  let me;
  try{ me = await apiGet("/api/me"); }
  catch(err){ app().innerHTML = '<div class="login"><div class="brand"><img src="icon.svg" alt=""><b>REL-UNITY</b><span>Can\'t reach the factory server — check the Wi-Fi.</span></div><button class="btn primary" onclick="boot()">'+svg("refresh")+'Retry</button></div>'; return; }
  if(!me || me.__auth===false || !me.user){ return renderLogin(); }
  USER = me.user; await loadDB(); route();
}
boot();
