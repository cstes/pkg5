#!/usr/bin/python
#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at usr/src/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END
#

#
# Copyright (c) 2010, 2016, Oracle and/or its affiliates. All rights reserved.
#

from . import testutils
if __name__ == "__main__":
        testutils.setup_environment("../../../proto")

import pkg5unittest
import pkg.solver as solver
import os
import sys

class TestSolver(pkg5unittest.Pkg5TestCase):

        def test_no_solution(self):
                cnf_test(failing_test_case.splitlines())

        def test_solution(self):
                cnf_test(working_test_case.splitlines())

def cnf_test(lines):
        s = solver.msat_solver()
        
        for l in lines:
                if l and l[0] in 'pc%0':
                        pass # comment
                else:
                        # skip trailing 0
                        cl = [int(i) for i in l.split()[0:-1]]
                        if cl and not s.add_clause(cl):
                                return False
        # create new copy of solver instance to test copy code
        n = solver.msat_solver(s)
        del s # force gc of old solver instance
        return n.solve([])


failing_test_case = """
c This Formular is generated by mcnf
c
c    horn? no
c    forced? no
c    mixed sat? no
c    clause length = 3
c
p cnf 250  1065
 -128 -209 148 0
2 196 -115 0
-66 -189 -241 0
-84 -132 -93 0
214 179 66 0
203 132 -237 0
164 -13 -172 0
-157 198 160 0
-91 -164 235 0
-70 -116 54 0
-164 171 -189 0
126 -184 211 0
-19 118 41 0
32 105 -33 0
-141 -108 50 0
-1 156 -188 0
138 -181 142 0
-191 -247 -220 0
-101 -207 -88 0
68 114 -234 0
134 -57 -131 0
-30 -133 116 0
-24 -173 92 0
226 -4 -224 0
-190 204 61 0
148 205 -174 0
213 -56 53 0
174 -250 206 0
32 219 -112 0
203 -222 202 0
130 42 226 0
222 33 58 0
58 35 34 0
-121 80 245 0
-231 38 -248 0
-205 -179 184 0
-182 -204 -36 0
23 35 -181 0
82 -168 -59 0
103 132 -182 0
-243 -18 -160 0
-180 130 95 0
111 -140 -107 0
19 28 -72 0
-222 207 -103 0
134 -50 -184 0
185 155 -11 0
-102 230 -18 0
-112 39 242 0
154 -87 53 0
173 -123 -159 0
-238 -101 -40 0
-126 -232 -139 0
107 -51 197 0
-194 -138 -150 0
106 -66 -11 0
-150 -159 -27 0
-98 -32 138 0
144 -32 128 0
153 74 -249 0
-190 -175 -208 0
-127 88 -38 0
-59 125 -225 0
-23 4 181 0
12 247 -133 0
151 -238 127 0
237 -65 -154 0
-218 -26 -55 0
91 -245 169 0
-81 -156 10 0
166 -66 -45 0
109 -162 47 0
-193 153 40 0
162 -186 -7 0
93 38 -58 0
-159 -167 -39 0
-187 68 124 0
247 23 212 0
49 182 -243 0
206 -105 -237 0
236 116 154 0
236 -6 182 0
-168 236 35 0
-186 70 -236 0
127 80 103 0
100 79 -176 0
117 -88 -1 0
60 -115 -224 0
-148 181 -65 0
-132 235 19 0
-44 -197 190 0
-214 67 129 0
-203 175 -191 0
-172 166 -115 0
-176 -180 207 0
-56 -208 -1 0
-37 140 -19 0
-242 -55 58 0
-116 -153 241 0
-203 64 -219 0
-214 64 90 0
-166 96 155 0
68 -2 63 0
-200 49 196 0
-230 -232 -148 0
-81 105 219 0
187 -236 -123 0
-99 237 136 0
-205 61 -118 0
-235 -230 128 0
38 -9 -124 0
-34 -116 179 0
-40 -55 -85 0
244 170 6 0
-7 -54 -236 0
153 -223 173 0
-219 -13 -217 0
244 -210 -228 0
23 -128 -113 0
35 -245 -235 0
184 31 143 0
-207 -24 135 0
97 -165 -14 0
-17 15 26 0
61 78 -8 0
215 -30 -166 0
229 93 -246 0
-167 -113 80 0
78 205 -87 0
117 -144 207 0
-10 153 -84 0
-147 238 61 0
-58 -17 -190 0
209 -25 -81 0
-175 244 -57 0
185 127 -147 0
237 199 -144 0
124 148 -10 0
190 244 231 0
-185 214 -101 0
-237 31 -94 0
-39 36 -94 0
-175 206 81 0
141 -209 -109 0
228 -165 -112 0
-45 142 238 0
-34 -64 -71 0
-60 170 -109 0
6 245 87 0
12 -93 -231 0
80 216 28 0
-103 137 116 0
-77 -73 -30 0
-63 219 -129 0
-215 -94 86 0
81 46 221 0
161 -215 -212 0
-137 -215 48 0
-50 211 229 0
172 74 154 0
-14 -100 166 0
59 -119 -243 0
244 -31 -96 0
51 -247 205 0
-90 97 -139 0
113 118 -7 0
57 -161 -84 0
180 -174 -9 0
-19 16 -202 0
-39 -134 224 0
84 240 195 0
-55 75 -207 0
116 54 60 0
80 98 40 0
-159 109 217 0
-210 -119 82 0
-201 -14 174 0
43 -19 -100 0
-126 223 26 0
-249 163 -205 0
-58 -4 109 0
-239 109 -82 0
210 -58 -2 0
238 -36 117 0
109 -199 32 0
-54 221 -80 0
230 99 97 0
45 221 169 0
191 17 114 0
-177 -138 -12 0
35 -5 145 0
-102 -147 103 0
-59 3 84 0
-56 240 -130 0
-233 -223 -47 0
169 216 -3 0
-68 -182 67 0
34 -189 27 0
230 -222 66 0
19 123 84 0
64 35 231 0
236 165 242 0
77 -119 -61 0
-179 215 198 0
-105 -93 211 0
-204 221 -112 0
-244 23 -125 0
-107 152 78 0
144 -183 28 0
-179 -32 194 0
217 174 72 0
-38 101 -132 0
-122 193 108 0
12 3 -44 0
140 -23 -2 0
185 -129 145 0
-116 -245 -102 0
203 -29 -131 0
-172 239 243 0
-186 -167 109 0
158 -184 149 0
-53 56 100 0
-92 5 35 0
-212 -236 250 0
-42 137 -193 0
171 231 127 0
176 -85 -122 0
32 81 -178 0
78 -14 -227 0
104 -10 -65 0
239 -81 -118 0
182 76 -235 0
-226 -132 54 0
145 25 120 0
49 205 99 0
250 240 -89 0
17 37 -65 0
226 -66 -47 0
136 -112 19 0
-94 -32 74 0
200 144 -65 0
27 29 207 0
6 112 53 0
-170 -192 -65 0
-18 206 8 0
-158 245 147 0
222 34 24 0
69 182 -121 0
-22 -202 -232 0
-213 -82 173 0
78 -176 -151 0
245 215 242 0
-126 -96 243 0
-164 -220 205 0
-60 128 162 0
-237 -126 -20 0
105 -144 -165 0
-158 76 -38 0
153 -236 206 0
187 -191 247 0
-192 159 171 0
162 -151 -213 0
19 155 238 0
-43 207 -46 0
117 250 118 0
159 40 -199 0
149 -163 -145 0
23 7 46 0
71 106 56 0
-43 220 -118 0
-200 242 6 0
143 219 -168 0
-179 102 -163 0
-74 183 -82 0
248 92 -154 0
81 202 229 0
92 243 19 0
165 -210 199 0
-54 -8 244 0
-70 -135 -223 0
-80 -89 -189 0
-7 182 -16 0
172 53 8 0
114 -107 197 0
-135 -35 -239 0
-214 -10 137 0
136 -131 151 0
15 -37 -89 0
-234 -7 97 0
118 191 101 0
215 123 185 0
-230 202 -190 0
211 -59 210 0
200 -162 116 0
158 12 212 0
-56 229 196 0
-50 -52 218 0
164 -142 -71 0
233 -140 159 0
119 93 65 0
155 -156 -57 0
117 -197 180 0
-97 -100 -2 0
165 206 83 0
-127 173 -110 0
20 158 116 0
-205 -125 -209 0
-244 -57 -246 0
-139 -173 21 0
89 -150 149 0
-51 60 -224 0
-81 -193 195 0
-208 -209 83 0
-141 70 -223 0
200 -121 99 0
-207 201 -61 0
167 157 -71 0
200 78 182 0
82 171 -183 0
4 -33 -85 0
-103 87 186 0
41 183 169 0
84 244 -116 0
128 -108 -67 0
24 165 181 0
94 118 -148 0
-41 -71 -98 0
248 15 -135 0
10 -157 -17 0
-225 241 93 0
217 -192 227 0
28 -11 78 0
-16 218 24 0
59 -91 -210 0
4 141 166 0
-204 12 -206 0
187 153 -186 0
23 -43 -124 0
100 2 -46 0
-236 -80 -102 0
165 129 159 0
-45 245 -187 0
137 31 -7 0
214 -178 200 0
222 107 -74 0
-37 -161 -129 0
-202 -214 99 0
69 3 78 0
-7 -217 51 0
215 -99 96 0
124 41 195 0
-233 -223 206 0
233 197 87 0
-102 33 70 0
175 241 162 0
86 -202 83 0
137 -214 64 0
-111 -204 197 0
-23 12 -121 0
101 28 -95 0
-206 57 220 0
-122 -2 -125 0
75 -241 86 0
-72 185 77 0
-125 210 -143 0
106 36 54 0
136 142 -93 0
-142 -180 214 0
44 -22 -60 0
-235 88 -130 0
-124 -162 245 0
19 -121 156 0
84 -23 -191 0
-173 -43 -163 0
151 148 213 0
-239 147 -180 0
-247 -92 -36 0
163 37 -188 0
-245 -7 -231 0
-32 -139 41 0
-13 -157 211 0
-107 136 126 0
-58 201 -115 0
-184 -48 -205 0
57 -237 -80 0
160 -243 155 0
154 -42 -179 0
-107 -242 -167 0
169 170 -19 0
-65 -140 -209 0
143 146 182 0
90 -170 158 0
-235 54 83 0
-122 193 239 0
112 130 -212 0
-9 -167 93 0
-57 54 -28 0
-55 -56 29 0
-206 -79 245 0
-16 -81 -190 0
174 160 131 0
-125 156 -148 0
-128 174 -25 0
-209 -16 60 0
-13 -225 109 0
167 -124 168 0
142 -16 173 0
8 -45 216 0
13 160 -41 0
-101 125 -225 0
-218 244 -49 0
153 -183 204 0
117 230 167 0
-108 24 -27 0
149 -198 13 0
48 124 -84 0
-35 -162 58 0
110 -103 9 0
-143 -43 169 0
-91 -87 -70 0
11 -117 244 0
-141 37 -177 0
238 126 -215 0
157 103 -27 0
-133 134 -3 0
112 -107 -113 0
-225 -104 26 0
109 -220 -174 0
58 -140 -86 0
1 97 14 0
249 161 -217 0
99 -242 33 0
172 2 -235 0
-79 -132 107 0
43 -217 -169 0
-166 218 -128 0
63 178 135 0
110 224 30 0
-62 147 -237 0
-241 -103 -169 0
125 -75 -106 0
146 20 -112 0
59 226 -136 0
-194 132 -101 0
133 -41 -14 0
190 74 -247 0
230 221 224 0
-3 -61 -65 0
93 15 194 0
-155 105 117 0
-146 -127 -35 0
170 -173 213 0
-13 -234 -117 0
-244 -225 15 0
-41 151 -185 0
-196 -2 114 0
-220 111 -238 0
234 134 146 0
100 -29 -4 0
-195 -6 151 0
-116 109 -9 0
45 -58 -61 0
195 224 66 0
119 174 129 0
122 233 100 0
30 -227 -120 0
238 1 16 0
231 229 -46 0
188 226 23 0
-181 247 -216 0
233 84 97 0
8 41 71 0
37 52 56 0
-227 58 84 0
116 48 -95 0
-58 233 36 0
210 11 -116 0
-107 -103 242 0
21 -161 169 0
202 25 82 0
248 163 65 0
-108 26 -78 0
-162 163 -248 0
-14 -95 92 0
218 -151 -26 0
-132 -195 44 0
14 85 -136 0
-236 219 -105 0
164 136 -25 0
7 36 124 0
-163 -216 -15 0
-66 176 -76 0
-144 -3 -101 0
-178 -149 -108 0
175 -161 210 0
-118 106 -11 0
-124 128 98 0
-81 -223 117 0
154 149 -1 0
-186 26 66 0
-190 192 -114 0
-122 -197 -52 0
-84 -226 105 0
52 61 225 0
206 -7 -101 0
-29 93 -116 0
67 -164 135 0
1 -217 -5 0
-180 218 222 0
230 -225 -50 0
4 -25 45 0
-57 234 -1 0
-221 -103 100 0
137 234 -109 0
20 -227 -202 0
-103 -247 198 0
-29 -148 -35 0
-191 102 18 0
-52 -195 18 0
61 5 -247 0
165 -207 -217 0
-147 -207 27 0
100 117 -129 0
-152 -83 132 0
-190 53 -121 0
156 230 181 0
2 -239 -65 0
-55 -20 -107 0
-119 -39 -221 0
-116 147 16 0
-211 238 -60 0
249 -111 141 0
-54 -193 -81 0
49 -245 -5 0
-233 110 -109 0
-79 -56 180 0
-41 196 150 0
242 -63 231 0
39 22 100 0
5 23 204 0
-55 -100 105 0
-22 -28 247 0
-209 200 67 0
-46 59 62 0
-239 -107 -125 0
242 25 -246 0
-148 -30 -11 0
-148 160 -169 0
5 145 249 0
168 -28 -207 0
-188 212 -201 0
-166 205 -239 0
145 -246 -100 0
3 215 -93 0
101 -198 -160 0
-233 178 -90 0
-143 -26 -102 0
-72 -97 -195 0
-119 -163 -120 0
93 13 98 0
-131 -53 15 0
-118 129 151 0
168 81 199 0
-17 121 -21 0
-36 -175 196 0
-221 57 68 0
111 145 -183 0
114 -31 24 0
-170 159 -146 0
123 -80 152 0
-84 -184 -134 0
-206 30 -55 0
81 -154 198 0
129 135 248 0
-2 198 122 0
230 101 -18 0
25 208 216 0
-247 176 160 0
34 -159 9 0
-74 184 31 0
29 -66 -148 0
-233 204 -107 0
204 -30 -127 0
-237 8 -65 0
79 112 181 0
157 -85 83 0
204 113 -216 0
-11 -15 27 0
44 114 8 0
105 188 -158 0
-51 204 -48 0
145 211 40 0
-107 -31 -114 0
-134 212 -105 0
188 -174 -151 0
58 -9 -151 0
33 -37 -119 0
172 -3 169 0
-26 -21 48 0
-94 -99 -41 0
192 1 -7 0
250 -138 185 0
-6 -131 -83 0
11 191 -240 0
-175 -163 -249 0
-214 -98 193 0
120 190 -185 0
-135 -64 -24 0
-187 249 -129 0
76 -232 112 0
-17 -161 117 0
-6 250 246 0
85 -188 117 0
-47 91 -103 0
-123 -92 142 0
3 -183 -249 0
-175 148 -129 0
223 172 119 0
194 76 -114 0
206 123 -222 0
-186 -110 -71 0
-63 152 -110 0
-122 -44 -119 0
-14 76 -224 0
-8 -77 -97 0
-116 110 63 0
148 106 192 0
204 -168 -56 0
-221 173 -13 0
168 57 -211 0
218 151 245 0
70 -234 -143 0
24 194 106 0
16 -236 -187 0
162 97 43 0
8 79 228 0
-39 -179 48 0
-119 213 -231 0
-239 57 -232 0
-161 247 8 0
30 -127 197 0
72 168 -233 0
-157 -217 -135 0
134 180 233 0
27 -14 -64 0
153 247 -60 0
-154 -76 -106 0
-59 -100 170 0
120 -121 -41 0
-169 13 158 0
-166 199 120 0
164 202 -199 0
-223 148 -242 0
4 211 100 0
188 -231 -98 0
218 129 -93 0
-211 18 -93 0
51 -10 -78 0
22 -155 -130 0
207 -135 -172 0
199 197 14 0
182 -245 -135 0
-204 181 -32 0
-18 -237 80 0
-96 69 193 0
-98 245 -91 0
71 -24 93 0
48 -131 194 0
29 144 -12 0
128 15 -71 0
125 58 -238 0
-84 111 38 0
224 168 246 0
-82 -188 -33 0
-67 98 242 0
34 248 -112 0
217 95 59 0
56 245 13 0
72 129 -245 0
82 134 -61 0
-128 55 -183 0
-187 42 38 0
90 -102 54 0
-159 224 229 0
-117 -158 -180 0
113 108 5 0
239 34 -122 0
-85 -118 -19 0
-240 129 -145 0
-15 149 129 0
-144 -189 217 0
228 -223 97 0
16 -84 -242 0
206 -212 91 0
-71 -194 21 0
59 -31 37 0
-89 156 -243 0
60 21 75 0
14 12 -8 0
-227 -183 131 0
-95 -190 -49 0
-151 -54 -133 0
-134 49 -157 0
6 -114 224 0
201 -195 -17 0
-99 -36 88 0
123 -67 105 0
142 -94 49 0
58 106 234 0
22 -18 -86 0
201 -245 71 0
-220 -228 227 0
-117 31 -212 0
-177 -140 -59 0
229 233 150 0
47 -36 103 0
-239 102 -241 0
-35 194 208 0
199 -37 -180 0
140 -176 -123 0
148 -36 243 0
14 141 227 0
-182 -141 248 0
178 85 144 0
247 231 15 0
77 -168 -40 0
-194 -181 -83 0
-225 116 -79 0
-80 182 -50 0
63 -36 -122 0
82 231 -59 0
-64 -244 157 0
-86 140 -207 0
-129 -192 -143 0
-69 227 216 0
-83 137 -101 0
117 -71 145 0
115 -53 199 0
-32 96 -1 0
104 93 -142 0
190 116 83 0
191 -124 -161 0
144 11 -181 0
-151 113 243 0
-66 -141 -108 0
-153 -149 7 0
-75 -129 137 0
113 -107 43 0
-191 99 237 0
199 67 163 0
-198 -177 -21 0
217 -236 88 0
-136 -84 158 0
52 68 -204 0
-61 200 21 0
95 -204 -221 0
-75 -125 118 0
213 113 173 0
-226 -92 118 0
-134 -189 67 0
-198 7 -26 0
-49 197 57 0
-5 -72 -146 0
226 167 -27 0
211 -229 94 0
-101 -80 -12 0
58 -47 -80 0
148 -217 -9 0
229 -120 -117 0
161 -174 191 0
10 -51 -154 0
-155 235 -198 0
-171 247 127 0
-130 19 140 0
-209 -185 -25 0
-223 -199 -27 0
-28 124 187 0
135 -28 31 0
-31 88 89 0
22 -43 -47 0
21 165 -184 0
-250 69 -27 0
221 -177 162 0
-72 -218 207 0
23 -159 83 0
-54 225 -190 0
-140 -21 49 0
-50 -177 -18 0
80 -250 172 0
-77 183 -218 0
184 55 -146 0
-104 181 -188 0
243 146 -70 0
-215 -187 -247 0
-196 -50 90 0
-84 143 -146 0
147 119 -118 0
227 14 -110 0
44 238 -153 0
197 -69 -176 0
127 65 27 0
208 190 -162 0
-39 250 -196 0
114 -89 206 0
142 75 -148 0
-202 237 -194 0
-21 216 -177 0
114 -80 -200 0
-27 91 -84 0
-63 249 -36 0
89 -18 -133 0
-19 -17 -107 0
145 62 -227 0
-89 -148 -44 0
-133 -192 -149 0
-65 240 -233 0
-88 -40 -245 0
92 -129 4 0
22 -62 -21 0
216 116 -93 0
79 100 234 0
39 134 44 0
-226 -170 -157 0
104 9 -191 0
26 -39 40 0
113 232 -174 0
-101 81 -104 0
173 90 101 0
-208 173 -97 0
-72 209 -111 0
-51 -93 108 0
-248 216 181 0
-65 -170 212 0
-102 -161 146 0
-72 -28 -25 0
-117 -18 229 0
-52 163 -79 0
94 120 79 0
105 116 -227 0
67 186 -211 0
-226 -235 196 0
-67 -11 23 0
-55 -85 -197 0
-200 -245 -76 0
109 -61 -127 0
-248 127 -229 0
53 148 -197 0
151 -98 -24 0
-58 180 -158 0
74 214 -200 0
-31 241 172 0
26 219 -56 0
1 110 -18 0
156 19 -89 0
112 87 204 0
-5 151 -59 0
34 -149 100 0
83 248 220 0
31 2 -78 0
110 -152 -37 0
-132 -217 -57 0
-71 176 79 0
31 -98 -75 0
-60 229 -171 0
87 207 112 0
30 151 -41 0
17 162 109 0
-172 111 -221 0
166 170 -147 0
-48 143 -201 0
233 -46 -122 0
207 -149 -124 0
-188 -166 -65 0
-76 -77 -96 0
-216 211 45 0
137 -103 -106 0
220 -82 -136 0
47 -84 -44 0
-37 67 -32 0
33 -5 156 0
-137 58 127 0
229 -36 -84 0
243 175 63 0
242 -73 -121 0
219 237 164 0
149 -201 -142 0
27 172 243 0
-90 29 45 0
206 57 153 0
-235 -49 -94 0
233 71 108 0
82 -122 223 0
-195 -71 37 0
-70 179 -159 0
-79 -240 -38 0
-79 -121 30 0
-238 -78 -246 0
218 96 48 0
107 -154 -199 0
4 -205 194 0
1 -205 -203 0
-155 129 -26 0
-128 57 22 0
-195 -168 -10 0
97 -186 -90 0
122 227 171 0
22 163 191 0
-223 191 -85 0
100 -59 -63 0
245 49 -181 0
-51 210 -135 0
-34 55 54 0
2 74 -57 0
233 168 -230 0
-40 22 230 0
128 -157 27 0
-154 -161 -114 0
-74 -136 38 0
51 -205 23 0
-212 40 -71 0
9 -138 -83 0
-95 54 121 0
-174 -85 140 0
66 16 67 0
-137 -8 105 0
-133 -206 -3 0
175 86 -206 0
-50 -217 51 0
51 244 31 0
184 -218 84 0
-153 58 -237 0
56 -198 63 0
228 -42 74 0
43 -32 245 0
-150 82 -44 0
-14 -22 25 0
228 -232 -245 0
-147 -221 29 0
-222 41 -40 0
42 -13 -20 0
53 9 161 0
125 236 69 0
-105 -172 32 0
-142 114 -71 0
-120 -122 -197 0
-29 9 -200 0
26 210 -193 0
-155 183 140 0
216 -208 -146 0
-220 -8 98 0
109 175 -63 0
-16 -139 -108 0
176 137 -119 0
-97 39 142 0
218 -44 -37 0
-119 -69 -107 0
-79 142 109 0
-123 25 227 0
177 -187 -89 0
-99 -147 -207 0
-68 81 236 0
145 90 3 0
93 -149 -127 0
-120 -67 154 0
121 234 -229 0
-245 186 21 0
92 5 -121 0
197 -100 -46 0
-40 -39 -3 0
25 -117 -121 0
-194 -189 175 0
246 10 40 0
13 50 147 0
-243 163 105 0
132 -131 -218 0
-241 78 101 0
-200 -38 -29 0
-36 -166 183 0
248 -216 218 0
-203 92 204 0
-83 -84 -165 0
-202 -197 -244 0
112 -221 63 0
100 151 -1 0
141 -206 -52 0
181 -208 -229 0
53 93 173 0
193 -184 -79 0
41 -78 -133 0
1 -35 -90 0
-198 -60 174 0
152 207 -157 0
183 -196 -163 0
-244 242 218 0
11 32 146 0
-66 -32 -84 0
-54 -109 -195 0
190 -116 144 0
-242 -122 86 0
-71 7 -150 0
241 -173 -15 0
62 -217 81 0
205 -116 130 0
193 -209 128 0
146 -240 -132 0
29 197 161 0
15 83 -39 0
-109 -44 81 0
244 85 -7 0
-246 9 165 0
115 -83 67 0
-98 -141 170 0
-102 94 -52 0
-231 -74 -28 0
162 191 -149 0
197 -183 -35 0
102 -56 50 0
30 -45 -129 0
25 -207 -33 0
192 -106 -169 0
43 -129 -169 0
237 244 182 0
-72 -44 -168 0
-158 -150 102 0
168 -143 151 0
-72 26 212 0
116 -89 98 0
171 -197 156 0
233 -54 -181 0
129 -161 25 0
113 69 -33 0
179 -175 224 0
138 -143 -46 0
75 213 -246 0
-137 -175 -150 0
-169 -67 215 0
86 69 -199 0
-159 233 63 0
-145 101 6 0
129 -243 -227 0
-175 72 -247 0
163 -109 207 0
31 77 33 0
-136 175 160 0
-192 -193 -7 0
99 145 232 0
-233 198 114 0
240 -89 -108 0
-81 -67 -63 0
5 149 69 0
-172 166 -184 0
158 -244 -166 0
-53 -172 -62 0
49 25 61 0
237 19 -166 0
94 202 -148 0
-246 13 152 0
-135 -86 -5 0
-190 -44 -223 0
-17 -141 6 0
165 39 237 0
221 -62 -104 0
-206 107 -223 0
-159 -243 -13 0
118 -9 57 0
%
0
"""
working_test_case = """
c This Formular is generated by mcnf
c
c    horn? no
c    forced? no
c    mixed sat? no
c    clause length = 3
c
p cnf 250  1065
 -108 246 59 0
-161 -43 234 0
7 41 -88 0
26 178 -41 0
-7 -145 -33 0
206 18 -136 0
-15 173 -213 0
31 -91 215 0
3 216 196 0
234 -85 179 0
155 -195 106 0
-211 -223 -41 0
97 2 -217 0
-81 -122 27 0
-149 34 239 0
69 -216 183 0
-69 148 -92 0
-89 -120 184 0
231 110 -213 0
67 173 -195 0
132 155 183 0
-115 83 4 0
173 163 -242 0
-198 43 90 0
71 -116 37 0
-232 52 28 0
21 -230 -124 0
-146 -108 -110 0
-116 163 214 0
69 -143 128 0
228 141 -99 0
-47 75 -193 0
-118 -244 -235 0
148 -246 -112 0
124 19 -76 0
-49 102 -125 0
110 155 3 0
-180 -192 -94 0
-114 -67 -219 0
-159 53 187 0
219 -102 162 0
21 -109 -173 0
-124 90 189 0
-191 117 175 0
77 -250 -155 0
-74 203 60 0
-4 65 166 0
174 -212 -165 0
-220 119 -35 0
-247 105 126 0
-110 -192 63 0
-227 181 172 0
-219 -31 -221 0
51 113 19 0
212 -4 151 0
197 -14 -211 0
117 159 -69 0
48 -19 207 0
-168 203 -212 0
-232 250 -222 0
151 34 139 0
249 -159 229 0
-243 244 -48 0
48 180 -153 0
-227 -98 190 0
-73 -130 60 0
33 239 -11 0
41 -48 -201 0
-39 43 143 0
131 -28 106 0
-97 49 -215 0
7 42 -194 0
-224 -94 46 0
137 -220 -84 0
-38 41 -163 0
-229 208 -187 0
149 -120 238 0
-90 111 135 0
176 -171 -36 0
144 -238 237 0
-194 111 -55 0
76 203 -38 0
-105 134 34 0
55 -194 -239 0
37 -95 177 0
-121 -94 -169 0
-93 49 -175 0
54 -217 102 0
-155 11 63 0
83 -138 109 0
-68 -30 103 0
-208 -48 -125 0
-100 230 -204 0
-70 222 171 0
146 -198 158 0
13 24 98 0
191 217 100 0
52 -198 5 0
166 219 -43 0
107 -247 105 0
-83 -13 86 0
232 -68 -61 0
-107 185 -112 0
-106 225 -226 0
48 71 238 0
144 -83 -135 0
-56 -27 -39 0
243 94 55 0
38 139 35 0
-146 -127 180 0
182 -83 84 0
45 211 -70 0
31 -91 72 0
-146 -232 244 0
-39 140 -200 0
219 205 -220 0
-94 -65 -87 0
-143 180 -24 0
70 161 -201 0
136 128 85 0
-223 64 62 0
-69 209 147 0
88 -15 -225 0
80 48 -149 0
224 246 -117 0
-166 -53 -26 0
-59 -63 -100 0
-1 -55 -237 0
214 246 13 0
-101 249 -118 0
-180 -222 -250 0
-97 -7 58 0
-169 -213 -80 0
-120 152 242 0
5 115 15 0
70 -12 -43 0
65 63 -248 0
-148 177 173 0
-224 201 12 0
-231 -88 -141 0
66 29 -233 0
99 163 12 0
-56 -183 197 0
89 133 229 0
126 79 149 0
-238 -139 -137 0
-170 -95 -148 0
-202 -246 115 0
-176 -63 158 0
216 38 -83 0
221 41 44 0
-91 181 135 0
171 -63 71 0
-60 136 107 0
222 5 57 0
210 -89 -151 0
-44 36 -91 0
3 -194 -15 0
-117 38 -110 0
242 226 155 0
158 -240 110 0
218 -37 90 0
11 217 57 0
250 -157 73 0
-9 -122 53 0
185 -76 73 0
-99 -101 102 0
52 -171 33 0
-143 195 228 0
42 -63 -229 0
-178 -160 224 0
-65 -54 208 0
232 -43 -38 0
85 43 -178 0
-171 -50 45 0
47 71 -180 0
127 135 -187 0
-201 33 222 0
-221 -131 -165 0
-131 114 221 0
195 60 185 0
-8 206 -140 0
124 -240 223 0
-217 198 149 0
52 -227 -206 0
136 -96 29 0
-76 -228 64 0
-157 -47 93 0
148 -108 17 0
139 40 -89 0
63 198 86 0
199 94 -33 0
-116 216 -2 0
27 242 -1 0
-156 177 28 0
234 -83 37 0
-124 -123 -149 0
112 -1 173 0
7 235 10 0
245 -184 -224 0
-112 -161 77 0
203 104 124 0
-59 -123 -10 0
250 -242 -203 0
56 243 164 0
24 126 -2 0
-101 227 86 0
-233 138 -218 0
-211 -119 -196 0
143 -183 -186 0
-148 236 76 0
-131 -187 -77 0
62 -144 -43 0
-232 96 -30 0
121 -152 89 0
7 105 37 0
182 135 -58 0
-164 -162 -112 0
-118 173 93 0
-54 220 -2 0
-193 32 65 0
-101 46 203 0
-127 -219 -215 0
235 -42 -77 0
-179 -242 -145 0
-140 77 203 0
-23 157 -112 0
-28 -193 134 0
-147 -166 100 0
148 171 -31 0
-214 241 -166 0
-217 204 93 0
-219 -211 -142 0
107 57 50 0
227 220 119 0
-234 62 24 0
-131 -223 24 0
232 133 -4 0
74 200 -201 0
211 6 220 0
-113 -9 102 0
-207 39 -80 0
24 244 -125 0
171 190 -167 0
122 24 -201 0
-132 216 -235 0
-90 58 -181 0
161 62 185 0
-3 -9 242 0
115 2 -78 0
42 -225 -145 0
168 -46 55 0
-40 -126 -154 0
26 164 -1 0
-71 199 -133 0
-78 55 -201 0
219 249 -203 0
116 137 -43 0
11 -137 -118 0
143 224 -150 0
-2 -199 218 0
108 -140 -47 0
228 28 -30 0
224 58 -27 0
-42 -211 153 0
104 -238 -222 0
-120 47 -33 0
61 85 223 0
230 -78 -77 0
185 -210 106 0
111 4 80 0
226 195 -66 0
-204 172 8 0
195 -241 191 0
166 182 -69 0
-114 -130 223 0
213 -189 243 0
-201 151 26 0
70 21 28 0
-119 -208 -207 0
-156 94 106 0
-177 250 -6 0
24 -227 -103 0
87 4 -200 0
139 133 -200 0
-71 226 23 0
-244 -32 60 0
202 225 -63 0
-233 -111 1 0
175 -114 -147 0
54 -30 193 0
-137 -199 78 0
31 -149 3 0
90 186 138 0
105 -43 -227 0
-218 220 -216 0
206 -182 119 0
62 158 -215 0
-92 -91 -103 0
92 35 -13 0
-4 -148 -219 0
-119 125 8 0
214 -160 -39 0
120 -1 59 0
190 216 -43 0
-11 -5 119 0
-118 -36 -187 0
-200 -152 98 0
194 -50 -8 0
32 88 -154 0
-45 106 159 0
-226 202 112 0
-101 28 -201 0
-206 -209 180 0
152 244 165 0
210 112 -115 0
195 -1 -151 0
104 -14 5 0
185 -167 -229 0
192 31 184 0
-116 -46 -113 0
178 -108 140 0
56 17 67 0
80 6 195 0
-250 -61 -106 0
184 31 -236 0
185 188 -7 0
-127 -72 187 0
-221 212 -13 0
240 -19 192 0
36 -135 -139 0
-170 -116 87 0
96 66 173 0
40 -229 16 0
184 -134 55 0
233 13 141 0
19 -204 -188 0
-208 226 -192 0
-185 48 178 0
236 -34 -204 0
-46 141 -194 0
-8 -30 181 0
72 -92 37 0
-212 157 -92 0
-210 -92 -225 0
95 176 23 0
-16 120 -63 0
7 -136 40 0
-88 -110 168 0
121 208 -115 0
228 215 171 0
35 -19 -151 0
45 222 -101 0
95 103 108 0
-35 -152 -64 0
144 -226 -149 0
-95 11 -170 0
211 -152 106 0
-59 80 223 0
22 126 -156 0
-19 -167 128 0
-68 76 -114 0
-121 32 122 0
96 152 187 0
-72 -90 -152 0
129 193 93 0
-109 -177 -149 0
193 35 2 0
172 -106 246 0
134 -245 152 0
212 100 -19 0
127 -214 -56 0
-245 -128 3 0
89 -114 119 0
147 -105 37 0
-125 -102 -108 0
22 33 177 0
46 52 -240 0
-62 -136 45 0
222 -117 120 0
16 -40 111 0
86 206 49 0
123 -78 -158 0
44 188 90 0
-103 89 176 0
232 -112 130 0
-109 70 19 0
-15 204 128 0
-127 -110 192 0
-26 52 -147 0
-41 5 105 0
234 206 -160 0
-52 128 195 0
-184 -176 121 0
184 167 -120 0
-74 158 -148 0
-18 62 200 0
169 115 -190 0
-124 229 164 0
-63 37 221 0
-76 190 245 0
-217 136 -134 0
-228 231 62 0
156 -218 -85 0
124 -25 225 0
-182 32 -31 0
-250 -221 35 0
-80 114 -78 0
248 186 139 0
-19 -128 125 0
85 154 113 0
14 -80 -88 0
-145 -43 88 0
145 181 55 0
134 31 -187 0
-89 -109 -62 0
-68 237 -222 0
-130 -180 -227 0
-86 48 90 0
-199 -215 -132 0
44 60 -14 0
-248 -79 224 0
-154 114 189 0
-39 167 -139 0
230 -5 -184 0
17 184 -215 0
-17 37 54 0
-249 159 -151 0
-29 -78 -148 0
136 186 209 0
-224 64 33 0
-163 111 108 0
-4 99 23 0
137 -64 138 0
-237 -116 29 0
44 158 -139 0
147 -8 -92 0
-118 -228 42 0
201 19 141 0
-182 -39 -238 0
-36 27 -79 0
-157 249 -181 0
-191 121 132 0
-59 212 32 0
72 -233 122 0
230 -229 -132 0
-231 60 -233 0
-66 -249 106 0
-210 -40 -79 0
-75 61 111 0
-51 -98 -32 0
-166 137 245 0
-134 113 52 0
-107 19 72 0
-64 85 -121 0
227 82 -87 0
-194 180 -128 0
241 -211 38 0
-74 -56 115 0
206 -54 -210 0
-66 -204 72 0
144 156 16 0
-197 84 54 0
-80 199 59 0
69 49 103 0
19 190 -34 0
-176 235 -151 0
33 -202 -78 0
-90 -15 -151 0
198 28 -43 0
-131 -74 -108 0
159 89 -184 0
-54 -62 141 0
-83 -238 91 0
227 -84 -76 0
187 -15 205 0
-243 -87 -207 0
115 200 -48 0
-82 -163 184 0
221 -122 153 0
-178 77 -52 0
-250 113 -65 0
-192 -153 -161 0
185 -240 153 0
187 -133 171 0
-127 -108 139 0
-158 -240 -121 0
183 -137 -62 0
-84 -60 210 0
-35 -115 -5 0
-16 81 41 0
163 -167 -20 0
192 -71 -102 0
-223 -248 -37 0
54 -18 79 0
242 -238 114 0
64 55 -39 0
-48 30 -248 0
-126 -6 -159 0
-127 242 -160 0
238 42 120 0
224 -138 -66 0
-189 -18 -183 0
99 -43 -220 0
149 -82 -59 0
-25 239 60 0
99 -201 137 0
-50 188 -223 0
84 147 157 0
240 -183 -212 0
239 243 -149 0
119 217 162 0
46 126 21 0
204 196 21 0
-174 26 53 0
-45 63 -15 0
155 -229 -99 0
-149 29 -51 0
43 250 -107 0
-183 -34 -169 0
7 -214 -55 0
154 -61 -143 0
-176 -25 -155 0
-138 235 201 0
137 -231 95 0
48 -223 -227 0
-16 -147 193 0
-34 75 94 0
140 -189 21 0
-152 70 49 0
-9 173 -238 0
118 -39 129 0
-129 -230 -101 0
7 -58 89 0
-96 50 -92 0
-158 54 -139 0
126 -156 -201 0
-31 94 127 0
32 72 103 0
-142 195 51 0
200 -246 -150 0
-1 17 94 0
-98 -52 -152 0
20 213 -38 0
-123 -225 -81 0
-19 -158 165 0
-107 -246 73 0
-9 45 145 0
-127 39 164 0
-34 95 130 0
-226 -210 213 0
-250 -201 -91 0
209 -191 -78 0
-245 -248 192 0
208 -191 -157 0
136 123 169 0
-117 -17 -74 0
-140 174 162 0
121 -37 119 0
124 -152 217 0
-240 -125 237 0
33 90 -20 0
-77 -187 -160 0
-109 24 -239 0
-3 -209 85 0
84 -229 -199 0
74 170 12 0
-79 102 -245 0
-191 -197 172 0
-111 -176 -216 0
-19 229 184 0
-139 -123 240 0
-208 45 -116 0
100 -224 151 0
-28 -13 -249 0
-198 -226 -122 0
-201 -81 43 0
205 -189 53 0
-23 240 -60 0
-246 38 -224 0
138 229 156 0
-179 -60 -221 0
204 -98 32 0
-46 -228 -178 0
-215 25 112 0
96 -34 198 0
32 -203 -225 0
231 -156 -232 0
130 -224 -197 0
196 156 209 0
99 210 -49 0
91 95 143 0
-199 79 -250 0
150 221 152 0
-31 223 249 0
4 -127 -73 0
-244 13 231 0
-231 -27 -156 0
159 -107 -217 0
-153 -234 -216 0
15 227 122 0
-223 -23 -56 0
-31 139 160 0
-183 28 -223 0
142 -241 -159 0
-102 -157 -109 0
17 -216 160 0
206 -200 207 0
-232 -70 -104 0
131 -110 182 0
171 70 -230 0
167 -58 189 0
145 -86 -57 0
177 -183 -13 0
-221 18 90 0
-225 228 -127 0
177 -174 226 0
222 -144 -191 0
-222 -171 -74 0
214 172 229 0
-111 49 12 0
-155 179 -192 0
-236 14 86 0
-68 -13 -1 0
103 210 -123 0
-116 124 -244 0
145 -14 -174 0
28 129 230 0
-192 123 35 0
143 -118 241 0
-211 -64 -128 0
201 -85 -1 0
91 198 24 0
-92 -2 -201 0
-158 87 83 0
152 63 94 0
17 218 119 0
-162 183 237 0
-13 -95 -49 0
179 129 -79 0
-42 -178 242 0
169 -224 227 0
76 152 1 0
-109 98 99 0
-150 240 -198 0
-158 -43 152 0
-159 -97 82 0
-203 210 223 0
208 132 -157 0
127 -189 -208 0
-48 -74 -1 0
-57 132 -26 0
-210 -220 -120 0
-241 -131 23 0
115 -64 -250 0
31 -185 -239 0
-210 190 94 0
144 -38 80 0
-155 211 134 0
-238 222 134 0
-153 74 205 0
-103 64 28 0
-57 -193 143 0
139 110 -73 0
-93 25 -153 0
-247 164 20 0
40 157 -189 0
172 160 -180 0
-177 -185 245 0
180 49 56 0
28 -22 232 0
172 13 193 0
97 1 206 0
-161 -242 -185 0
-186 170 -190 0
59 28 -236 0
76 246 222 0
64 -202 51 0
-20 138 107 0
96 -228 16 0
-249 28 44 0
-193 -143 -113 0
215 -224 -170 0
-131 -12 35 0
84 61 54 0
-116 94 50 0
-26 -21 -9 0
107 -150 -143 0
-174 45 147 0
34 -116 174 0
-109 -80 -113 0
25 -14 -212 0
203 9 -46 0
-231 -209 4 0
-239 200 151 0
181 146 -195 0
-234 79 195 0
-91 -65 -105 0
96 141 98 0
135 -6 215 0
150 -98 -147 0
-26 124 -30 0
-66 160 206 0
-60 -142 6 0
-173 -126 -28 0
138 -60 -43 0
235 -179 57 0
156 -215 34 0
-227 195 -221 0
6 -25 -87 0
228 49 -57 0
203 68 139 0
-133 237 -1 0
-247 74 -80 0
179 62 206 0
12 73 -165 0
-28 45 -65 0
-203 186 -132 0
-88 99 53 0
99 246 171 0
172 23 -88 0
-84 119 224 0
-44 -237 211 0
-155 -28 -163 0
-67 44 -224 0
3 19 7 0
-19 189 -216 0
-18 130 -237 0
-42 -210 -204 0
-183 -233 192 0
-141 222 -59 0
-244 80 -102 0
-210 90 68 0
123 110 -82 0
-226 -246 -231 0
206 -43 -172 0
178 -184 -63 0
217 103 224 0
-157 -172 -152 0
-236 -223 211 0
166 96 155 0
-70 38 -28 0
-18 34 23 0
-33 -224 -242 0
149 -197 213 0
-222 -79 198 0
-220 235 -95 0
-167 -135 194 0
10 159 -235 0
-241 242 143 0
55 -72 133 0
-59 -168 -33 0
64 81 -35 0
18 30 -70 0
198 -22 153 0
146 29 75 0
76 -89 189 0
10 55 -184 0
205 79 233 0
186 29 35 0
-91 14 37 0
187 -118 -155 0
-228 236 201 0
115 235 -90 0
-111 193 199 0
-153 122 80 0
-6 223 -239 0
57 -76 -200 0
18 -101 -214 0
-28 -59 -165 0
42 107 67 0
-243 -52 -77 0
-196 20 -249 0
125 -45 87 0
-60 -179 93 0
-169 196 -154 0
-89 60 -1 0
88 -237 233 0
-73 7 -53 0
193 -154 133 0
-82 46 232 0
-184 119 -109 0
-148 -121 136 0
-138 -30 24 0
145 -130 -23 0
63 -247 -195 0
-94 166 93 0
-103 -247 -246 0
6 -14 -232 0
-148 98 -50 0
69 -187 -212 0
237 76 -108 0
-205 130 204 0
-152 -124 93 0
54 -51 143 0
68 39 -204 0
222 39 11 0
-37 72 169 0
-69 173 160 0
206 -110 112 0
116 30 -121 0
4 29 210 0
-53 -144 -149 0
-7 202 -93 0
228 -69 -9 0
171 32 1 0
-212 104 -87 0
-249 -170 -89 0
-68 146 175 0
59 -39 105 0
39 48 -53 0
-98 -50 7 0
-129 221 -44 0
190 186 -79 0
151 -155 179 0
27 11 -104 0
-233 147 -242 0
-113 -210 183 0
-89 -118 237 0
-58 -132 -236 0
-42 -163 218 0
87 -225 -164 0
-40 -76 -204 0
24 -71 -249 0
91 46 -111 0
-33 -73 -161 0
-17 -54 127 0
-174 -172 -167 0
9 -168 -219 0
237 19 1 0
95 -128 105 0
157 144 127 0
124 247 180 0
-188 -134 -241 0
112 -127 187 0
-145 68 158 0
-73 228 179 0
-207 -135 249 0
-210 113 -6 0
119 -130 -23 0
-87 -138 -63 0
-30 -210 112 0
-210 116 -7 0
81 -211 43 0
233 30 -191 0
250 -171 -71 0
196 -194 168 0
-179 111 -191 0
-116 -150 153 0
-220 -219 -93 0
-94 224 99 0
122 232 207 0
115 -218 219 0
-247 -19 -187 0
214 147 143 0
234 150 -90 0
95 -185 -107 0
-160 -88 113 0
167 140 -33 0
-27 2 -106 0
35 42 61 0
249 219 59 0
2 180 120 0
-129 225 -151 0
-121 104 -192 0
-138 -57 -41 0
-73 179 -133 0
164 -36 -83 0
-45 -28 -116 0
135 60 47 0
76 173 125 0
-31 194 233 0
-67 239 -53 0
-40 67 -231 0
-98 -148 229 0
213 -50 187 0
141 197 2 0
-140 177 66 0
145 115 -155 0
44 117 65 0
-36 223 88 0
30 200 31 0
-212 237 174 0
-49 -177 167 0
-218 63 -148 0
-25 46 23 0
25 -54 226 0
163 -88 21 0
98 -41 -9 0
-98 -181 18 0
-182 -194 -137 0
-230 214 -46 0
240 182 9 0
93 -116 41 0
57 -228 186 0
165 154 -49 0
42 88 -202 0
8 33 -152 0
17 -136 -35 0
-62 45 141 0
-102 33 -18 0
138 -126 214 0
-59 -221 39 0
-130 4 -218 0
-78 123 250 0
83 221 -151 0
-225 8 110 0
-194 156 43 0
65 -245 34 0
-238 -237 217 0
106 -37 -56 0
240 111 184 0
-172 -243 185 0
245 40 -45 0
122 60 -189 0
-174 -152 181 0
155 -147 -178 0
117 -168 -219 0
-102 -127 234 0
99 26 -114 0
181 36 -62 0
178 169 116 0
81 -123 -30 0
-243 -26 -38 0
-31 20 217 0
55 239 -116 0
-85 -27 49 0
62 212 177 0
3 -4 127 0
-233 -9 68 0
-28 208 -114 0
23 159 240 0
125 171 83 0
152 16 97 0
-77 -39 -84 0
-19 -15 195 0
95 -180 177 0
204 -125 -207 0
-130 78 235 0
-51 182 79 0
122 -95 -80 0
85 -72 -167 0
48 -109 -41 0
-223 -25 -44 0
248 -51 -81 0
-141 57 -2 0
208 -207 -50 0
41 15 -63 0
48 -242 -232 0
240 196 -32 0
-227 -163 -23 0
207 -90 102 0
210 5 84 0
-230 -134 95 0
-193 214 239 0
-192 -11 173 0
-109 -196 145 0
30 -161 -113 0
216 164 83 0
103 67 21 0
102 -233 66 0
-79 56 -250 0
-82 -45 112 0
-144 -124 208 0
33 -37 -149 0
-109 230 173 0
-229 82 -174 0
179 137 -235 0
84 -225 -16 0
123 233 235 0
-211 144 92 0
-2 46 -177 0
115 -202 -119 0
241 75 174 0
-205 238 -105 0
-53 219 34 0
-239 103 -148 0
147 -143 123 0
-214 -232 188 0
10 -193 41 0
6 185 18 0
141 -68 -222 0
209 -129 -143 0
-194 -108 116 0
-184 5 -46 0
23 -125 -113 0
-159 54 -8 0
130 -50 119 0
156 -74 120 0
-124 139 -119 0
-97 -134 112 0
-150 -82 -79 0
148 91 219 0
-30 19 -172 0
-13 164 -15 0
-119 -179 -11 0
5 -38 -15 0
-4 94 -66 0
-71 140 -198 0
-119 -51 -151 0
9 50 162 0
-203 35 88 0
192 122 -127 0
-187 -164 -126 0
121 -25 -215 0
-5 -167 -196 0
216 138 -11 0
-86 46 250 0
199 239 -8 0
-238 244 188 0
98 -19 -11 0
19 -151 -83 0
-158 40 232 0
1 200 -23 0
171 -11 -139 0
-203 60 173 0
-160 -122 -8 0
-179 -58 1 0
-194 -216 -202 0
-111 144 -237 0
153 -206 9 0
-182 79 -233 0
-150 -249 -191 0
153 102 121 0
79 -178 -239 0
14 -79 196 0
133 84 193 0
-248 173 -13 0
-93 225 22 0
58 -158 -16 0
-36 236 -20 0
96 140 7 0
53 -2 202 0
235 -32 249 0
94 53 -234 0
50 134 -191 0
-243 -211 88 0
-28 52 94 0
3 101 65 0
78 200 -112 0
-16 -108 -93 0
-154 -169 242 0
-196 220 -177 0
-177 187 24 0
5 242 -195 0
81 157 -247 0
-191 -3 123 0
-16 115 10 0
-152 -217 33 0
-7 -149 67 0
105 45 23 0
-55 -23 109 0
-217 -220 -144 0
73 -63 149 0
-180 -245 -191 0
-113 -50 199 0
242 -205 52 0
129 98 -226 0
205 146 -200 0
145 -180 -182 0
-240 -39 176 0
217 166 -31 0
-24 -144 9 0
137 -120 -228 0
-24 -117 158 0
%
0
"""

if __name__ == "__main__":
        unittest.main()
