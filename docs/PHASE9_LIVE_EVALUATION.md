# Phase 9 Live Retrieval and Generation Evaluation

Model: `openai/gpt-oss-20b`  
Cases: 8  
Corpus: 15-course human-approved validation checkpoint

Each case records the exact query, expanded query, retrieved context and LLM answer.

## Audit summary

| Case | Retrieval assessment | Answer assessment |
|---|---|---|
| MCA Mathematics credits | Correct course | Grounded, but the answer omitted the required inline `[SOURCE 1]` marker |
| MBA selection | Correct course | Grounded and cited |
| M.Tech CSE details | Correct course | Cited; the extracted corpus repeats the merged intake value `20` on every specialization row, which needs source-table validation |
| MBBS requirements | Correct course | Grounded and cited |
| B.A.LL.B. duration and age | Correct course | Correctly answered duration and abstained on an unstated age limit |
| M.Sc. Ag. Microbiology qualification | Correct course | Grounded and cited |
| Postgraduate course discovery | MCA correctly ranked first | Answer used the relevant MCA source; ranks 2–3 were irrelevant candidates and should be improved during retrieval refinement |
| Diploma Engineering details | Correct course | Grounded and cited |

Direct-course retrieval selected the intended course in 7/7 cases. Course discovery placed the relevant course first, but only one of its three returned candidates was useful. Inline citation compliance was 7/8 answers.

## 1. I have 12 credits in Mathematics. Can I do M.C.A.?

**Retrieval mode:** hybrid retrieval

**Expanded query:** I have 12 credits in Mathematics. Can I do Master of Computer Science and Applications?

### Retrieved context

```text
[SOURCE 1]
Title: Master of Computer Science and Applications (MCA) - Complete Course Information
Citation: AMU Guide to Admissions 2026-27, page B.25
Content:
Course: Master of Computer Science and Applications (MCA)
Expanded Course Name: Master of Computer Science and Applications
Course Code: CAMSA
Faculty: Faculty of Science
Programme Level: postgraduate
Record Type: Course Profile

Qualifying Examination: B. Tech. / B.E. in relevant subject OR 03-year / 04-year B.Sc./ B.C.A. / B.Com. / B.A. from a recognized University and must have: a) Studied Mathematics as a subject with at least 16 credits at the qualifying examination. b) Studied Two courses of Computer Science out of which one should be any programming language. c) Studied Mathematics at 10+2 or equivalent level. d) Obtained 55% marks in aggregate or its equivalent grade in the qualifying examination.

Age Limit: Not more than 27 years as on 01 st July in the year of admission.

Selection Process: Through Admission Test.

Test Paper Details: There shall be one objective type paper of 100 marks comprising 100 Questions with the following breakup: a) Mathematics and Statistics : 30 Questions b) Physics : 20 Questions c) Computer Science : 50 Questions

Test Centre(s): The Admission Test shall be held at Aligarh (U.P.) only.

Course Details:
Row 1: Duration=4 Semesters; Course Code=CAMSA; Intake=60+6^

Source Pages: AMU Guide to Admissions 2026-27, page B.25 (physical page 94)
```

### LLM answer

You do not meet the Mathematics credit requirement for the MCA programme. The guide states that applicants must have studied Mathematics with at least **16 credits** at the qualifying examination, while you have only **12 credits**. Therefore, based on the provided guide evidence, you are not eligible to apply for the MCA programme.

### Sources

- `[SOURCE 1]` Master of Computer Science and Applications (MCA) - Complete Course Information — page B.25

## 2. How are candidates selected for M.B.A.?

**Retrieval mode:** hybrid retrieval

**Expanded query:** How are candidates selected for Master of Business Administration?

### Retrieved context

```text
[SOURCE 1]
Title: Master of Business Administration (MBA) - Complete Course Information
Citation: AMU Guide to Admissions 2026-27, page B.21
Content:
Course: Master of Business Administration (MBA)
Expanded Course Name: Master of Business Administration
Faculty: Faculty of Management Studies & Research
Programme Level: postgraduate
Record Type: Course Profile

Qualifying Examination: Bachelors degree in any discipline with at least 50% marks in aggregate.

Selection Process: Through Admission Test. The Total Merit will have the following components: a) Written Test : 100 Marks b) Interview/Aptitude Assessment/Group Discussion : 25 Marks Note: Candidates shall be called for Interview / Aptitude Assessment / Group Discussion on the basis of the performance in the written test. For the candidates who qualify written test, physical presence in the Interview / Aptitude Assessment / Group Discussion is compulsory to become eligible for selection.

Test Paper Details: There shall be one objective type paper of 100 marks comprising 100 questions on (i) Verbal Ability & Reading Comprehension : 25 Marks (ii) Data Interpretation and Logical Reasoning : 25 Marks (iii) Quantitative Ability : 25 Marks (iv) General Awareness : 25 Marks

Test Centre(s): The Admission Test shall be held at Aligarh (U.P.), Kolkata (W.B.) & Kozhikode (Kerala).

Additional Information: There shall be Combined Counselling for admission to MBA, MBA(IB) and MBA(Islamic Banking & Finance) .

Course Details:
Row 1: Duration=4 Semesters; Study Location=AMU, Aligarh; Course Code=BAMMA; Intake=60+9^
Row 2: Duration=4 Semesters; Study Location=AMU Center, Malappuram; Course Code=BAMMK; Intake=60+9^
Row 3: Duration=4 Semesters; Study Location=AMU Center, Murshidabad; Course Code=BAMMW; Intake=60+9^
Row 4: Duration=4 Semesters; Study Location=AMU Center, Kishanganj; Course Code=BAMMB; Intake=60

Source Pages: AMU Guide to Admissions 2026-27, page B.21 (physical page 90)
```

### LLM answer

Candidates for the Master of Business Administration (MBA) are selected through a two‑stage process:  

1. **Admission Test** – an objective paper of 100 marks (25 marks each in Verbal Ability & Reading Comprehension, Data Interpretation & Logical Reasoning, Quantitative Ability, and General Awareness).  
2. **Interview / Aptitude Assessment / Group Discussion** – 25 marks, called for candidates who qualify the written test; physical presence is compulsory for eligibility.  

The total merit is the sum of the written test and interview/assessment marks. The selection is conducted via combined counselling for MBA, MBA(IB) and MBA(Islamic Banking & Finance) [SOURCE 1].

### Sources

- `[SOURCE 1]` Master of Business Administration (MBA) - Complete Course Information — page B.21

## 3. What specializations, duration and intake are offered in M.Tech CSE?

**Retrieval mode:** hybrid retrieval

**Expanded query:** What specializations, duration and intake are offered in Master of Technology CSE?

### Retrieved context

```text
[SOURCE 1]
Title: Master of Technology (M. Tech.) – Computer Science & Engineering - Complete Course Information
Citation: AMU Guide to Admissions 2026-27, page B.11
Content:
Course: Master of Technology (M. Tech.) – Computer Science & Engineering
Expanded Course Name: Master of Technology
Faculty: Faculty of Engineering & Technology
Programme Level: postgraduate
Record Type: Course Profile

Qualifying Examination: B. Tech. or its equivalent examination in the relevant branch of study with not less than 60% marks in aggregate or its equivalent CPI/CGPA/NAG.

Selection Process: Based on candidate’s performance in GATE (applicable only for GATE qualified candidates with marks more than or equal to the qualifying marks of General Category, valid at the time of admission) as per the following priority: 1 st Priority: GATE in Computer Science and Information Technology 2 nd Priority: GATE in Electronics and Communication Engineering / Mathematics / Statistics / Geomatics Engineering Note: All other candidates shall be selected on remaining vacancies through Departmental Test.

Test Paper Details: There shall be one objective type paper.

Test Centre(s): The Departmental Test shall be held at Aligarh (U.P.) only.

Course Details:
Row 1: Duration=4 Semesters; Specialization=Software Engineering; Course Code=SPMEA; Intake=20
Row 2: Duration=4 Semesters; Specialization=Information Security; Course Code=IPMEA; Intake=20
Row 3: Duration=4 Semesters; Specialization=Computer Networks; Course Code=CPMEA; Intake=20

Source Pages: AMU Guide to Admissions 2026-27, page B.11 (physical page 80), AMU Guide to Admissions 2026-27, page B.11 (physical page 81)
```

### LLM answer

**M.Tech (CSE) – Specializations, Duration & Intake**

| Specialization | Duration | Intake |
|----------------|----------|--------|
| Software Engineering | 4 semesters | 20 students |
| Information Security | 4 semesters | 20 students |
| Computer Networks | 4 semesters | 20 students |

These details are taken from the AMU Guide to Admissions 2026‑27, page B.11. [SOURCE 1]

### Sources

- `[SOURCE 1]` Master of Technology (M. Tech.) – Computer Science & Engineering - Complete Course Information — page B.11

## 4. What are the eligibility and selection requirements for M.B.B.S.?

**Retrieval mode:** hybrid retrieval

**Expanded query:** What are the eligibility and selection requirements for Bachelor of Medicine and Bachelor of Surgery?

### Retrieved context

```text
[SOURCE 1]
Title: M.B.B.S. - Complete Course Information
Citation: AMU Guide to Admissions 2026-27, page A.9
Content:
Course: M.B.B.S.
Expanded Course Name: Bachelor of Medicine and Bachelor of Surgery
Course Code: MBBDA
Faculty: Faculty of Medicine
Programme Level: undergraduate
Record Type: Course Profile

Qualifying Examination: Senior Secondary School Certificate Examination of this University or an examination recognised by the University as its equivalent with Physics, Chemistry, Biology and English. Further, the candidate must have obtained a minimum of 50% marks in aggregate in Physics, Chemistry and Biology.

Age Limit: Not less than 17 years as on 31 st December in the year of admission.

Selection Process: Through NEET-UG of the registered candidates..

Additional Information: Selected candidates will have to go through medical fitness examination before completing the admission.

Course Details:
Row 1: Duration=4 ½ Years & 1 Year Compulsory Rotatory Internship; Course Code=MBBDA; Intake=145

Source Pages: AMU Guide to Admissions 2026-27, page A.9 (physical page 62)
```

### LLM answer

**Eligibility for M.B.B.S.**

- Must have passed the Senior Secondary School Certificate Examination of this University or an examination recognised by the University as its equivalent, with Physics, Chemistry, Biology and English.  
- Must have obtained a minimum of 50 % marks in aggregate in Physics, Chemistry and Biology.  
- Must be at least 17 years old as on 31 December of the year of admission.  
[SOURCE 1]

**Selection requirements for M.B.B.S.**

- Selection is made through NEET‑UG for registered candidates.  
- Selected candidates must undergo a medical fitness examination before completing admission.  
[SOURCE 1]

### Sources

- `[SOURCE 1]` M.B.B.S. - Complete Course Information — page A.9

## 5. How long is B.A.LL.B. and what is its age limit?

**Retrieval mode:** hybrid retrieval

**Expanded query:** How long is Bachelor of Arts and Bachelor of Laws and what is its age limit?

### Retrieved context

```text
[SOURCE 1]
Title: B.A.LL.B. - Complete Course Information
Citation: AMU Guide to Admissions 2026-27, page A.8
Content:
Course: B.A.LL.B.
Expanded Course Name: Bachelor of Arts and Bachelor of Laws
Faculty: Faculty of Law
Programme Level: undergraduate
Record Type: Course Profile

Qualifying Examination: Senior Secondary School Certificate or an equivalent examination with aggregate not less than 50% of the total marks. OR Bridge Course-Senior Secondary School Certificate from AMU with 50% marks in aggregate.

Selection Process: Through Admission Test

Test Paper Details: There shall be one paper of 100 marks consisting of 100 objective type questions on i) Proficiency in English : 40 marks ii) Current Affairs/General Knowledge (with emphasis on legal issues) : 40 marks iii) Reasoning and Aptitude : 20 marks

Test Centre(s): The Admission Test shall be held at Aligarh (U.P.), Kolkata (W.B.), & Kozhikode (Kerala).

Course Details:
Row 1: Duration=10 Semesters; Study Location=AMU, Aligarh; Course Code=LLBWA; Intake=120+24^
Row 2: Duration=10 Semesters; Study Location=AMU Center, Malappuram; Course Code=LLBWK; Intake=60
Row 3: Duration=10 Semesters; Study Location=AMU Center, Murshidabad; Course Code=LLBWW; Intake=60

Source Pages: AMU Guide to Admissions 2026-27, page A.8 (physical page 61)
```

### LLM answer

The B.A.LL.B. programme lasts **10 semesters** [SOURCE 1].  

The guide does not provide an age‑limit for this course, so the information is insufficient to answer that part.

### Sources

- `[SOURCE 1]` B.A.LL.B. - Complete Course Information — page A.8

## 6. What qualification is required for M.Sc. Ag Microbiology?

**Retrieval mode:** hybrid retrieval

**Expanded query:** What qualification is required for Master of Science Ag Microbiology?

### Retrieved context

```text
[SOURCE 1]
Title: M.Sc. (Ag.) Microbiology - Complete Course Information
Citation: AMU Guide to Admissions 2026-27, page B.1
Content:
Course: M.Sc. (Ag.) Microbiology
Expanded Course Name: Master of Science
Course Code: MBMGA
Faculty: Faculty of Agricultural Sciences
Programme Level: postgraduate
Record Type: Course Profile

Qualifying Examination: B.Sc. (Agriculture) / B.Sc. (Horticulture) / B.Sc. (Forestry) / B.Sc. (Biosciences) / B.Sc.(Microbiology) / B.Sc.(Industrial Microbiology) / B.Sc.(Biochemistry) / B.Sc. (Biotechnology) / B.Sc. (Bioinformatics) / B.Sc. (Molecular Biology) with not less than 55% marks in aggregate. OR B.Sc.(Life Sciences) with one of the subjects Zoology, Botany, Chemistry, Microbiology, Biotechnology as main and two as subsidiary subjects or any three subjects of equal value with not less than 55% marks in aggregate as well as the main subject.

Age Limit: Not more than 27 years as on 01 st July in the year of admission.

Selection Process: Through Departmental Test

Test Paper Details: There shall be one multiple choice objective type paper of 100 marks comprising a total of 100 questions with 30 questions on General Knowledge and General Awareness in Agricultural Sciences and related branches of Sciences / Life Sciences and 70 questions on Botany, Zoology, Biotechnology, Microbiology, Biochemistry and Chemistry.

Test Centre(s): The Departmental Test shall be held at Aligarh (U.P.) only.

Course Details:
Row 1: Duration=4 Semesters; Course Code=MBMGA; Intake=10+3*+2^

Source Pages: AMU Guide to Admissions 2026-27, page B.1 (physical page 70)
```

### LLM answer

The M.Sc. (Ag.) Microbiology requires a qualifying examination of a B.Sc. in one of the following subjects with at least 55 % marks in aggregate:  
- B.Sc. (Agriculture)  
- B.Sc. (Horticulture)  
- B.Sc. (Forestry)  
- B.Sc. (Biosciences)  
- B.Sc. (Microbiology)  
- B.Sc. (Industrial Microbiology)  
- B.Sc. (Biochemistry)  
- B.Sc. (Biotechnology)  
- B.Sc. (Bioinformatics)  
- B.Sc. (Molecular Biology)  

Alternatively, a B.Sc. (Life Sciences) with the main subject in Zoology, Botany, Chemistry, Microbiology, or Biotechnology and two subsidiary subjects (or any three equal‑value subjects) also qualifies, provided the aggregate marks are not less than 55 % [SOURCE 1].

### Sources

- `[SOURCE 1]` M.Sc. (Ag.) Microbiology - Complete Course Information — page B.1

## 7. I completed B.Sc. Computer Science. Which postgraduate courses in this guide may fit my background?

**Retrieval mode:** course discovery

**Expanded query:** I completed Bachelor of Science Computer Science. Which postgraduate courses in this guide may fit my background?

### Retrieved context

```text
[SOURCE 1]
Title: Master of Computer Science and Applications (MCA) - Complete Course Information
Citation: AMU Guide to Admissions 2026-27, page B.25
Content:
Course: Master of Computer Science and Applications (MCA)
Expanded Course Name: Master of Computer Science and Applications
Course Code: CAMSA
Faculty: Faculty of Science
Programme Level: postgraduate
Record Type: Course Profile

Qualifying Examination: B. Tech. / B.E. in relevant subject OR 03-year / 04-year B.Sc./ B.C.A. / B.Com. / B.A. from a recognized University and must have: a) Studied Mathematics as a subject with at least 16 credits at the qualifying examination. b) Studied Two courses of Computer Science out of which one should be any programming language. c) Studied Mathematics at 10+2 or equivalent level. d) Obtained 55% marks in aggregate or its equivalent grade in the qualifying examination.

Age Limit: Not more than 27 years as on 01 st July in the year of admission.

Selection Process: Through Admission Test.

Test Paper Details: There shall be one objective type paper of 100 marks comprising 100 Questions with the following breakup: a) Mathematics and Statistics : 30 Questions b) Physics : 20 Questions c) Computer Science : 50 Questions

Test Centre(s): The Admission Test shall be held at Aligarh (U.P.) only.

Course Details:
Row 1: Duration=4 Semesters; Course Code=CAMSA; Intake=60+6^

Source Pages: AMU Guide to Admissions 2026-27, page B.25 (physical page 94)

[SOURCE 2]
Title: Master of Technology (M. Tech.) – Computer Science & Engineering - Complete Course Information
Citation: AMU Guide to Admissions 2026-27, page B.11
Content:
Course: Master of Technology (M. Tech.) – Computer Science & Engineering
Expanded Course Name: Master of Technology
Faculty: Faculty of Engineering & Technology
Programme Level: postgraduate
Record Type: Course Profile

Qualifying Examination: B. Tech. or its equivalent examination in the relevant branch of study with not less than 60% marks in aggregate or its equivalent CPI/CGPA/NAG.

Selection Process: Based on candidate’s performance in GATE (applicable only for GATE qualified candidates with marks more than or equal to the qualifying marks of General Category, valid at the time of admission) as per the following priority: 1 st Priority: GATE in Computer Science and Information Technology 2 nd Priority: GATE in Electronics and Communication Engineering / Mathematics / Statistics / Geomatics Engineering Note: All other candidates shall be selected on remaining vacancies through Departmental Test.

Test Paper Details: There shall be one objective type paper.

Test Centre(s): The Departmental Test shall be held at Aligarh (U.P.) only.

Course Details:
Row 1: Duration=4 Semesters; Specialization=Software Engineering; Course Code=SPMEA; Intake=20
Row 2: Duration=4 Semesters; Specialization=Information Security; Course Code=IPMEA; Intake=20
Row 3: Duration=4 Semesters; Specialization=Computer Networks; Course Code=CPMEA; Intake=20

Source Pages: AMU Guide to Admissions 2026-27, page B.11 (physical page 80), AMU Guide to Admissions 2026-27, page B.11 (physical page 81)

[SOURCE 3]
Title: M.Sc. (Ag.) Microbiology - Complete Course Information
Citation: AMU Guide to Admissions 2026-27, page B.1
Content:
Course: M.Sc. (Ag.) Microbiology
Expanded Course Name: Master of Science
Course Code: MBMGA
Faculty: Faculty of Agricultural Sciences
Programme Level: postgraduate
Record Type: Course Profile

Qualifying Examination: B.Sc. (Agriculture) / B.Sc. (Horticulture) / B.Sc. (Forestry) / B.Sc. (Biosciences) / B.Sc.(Microbiology) / B.Sc.(Industrial Microbiology) / B.Sc.(Biochemistry) / B.Sc. (Biotechnology) / B.Sc. (Bioinformatics) / B.Sc. (Molecular Biology) with not less than 55% marks in aggregate. OR B.Sc.(Life Sciences) with one of the subjects Zoology, Botany, Chemistry, Microbiology, Biotechnology as main and two as subsidiary subjects or any three subjects of equal value with not less than 55% marks in aggregate as well as the main subject.

Age Limit: Not more than 27 years as on 01 st July in the year of admission.

Selection Process: Through Departmental Test

Test Paper Details: There shall be one multiple choice objective type paper of 100 marks comprising a total of 100 questions with 30 questions on General Knowledge and General Awareness in Agricultural Sciences and related branches of Sciences / Life Sciences and 70 questions on Botany, Zoology, Biotechnology, Microbiology, Biochemistry and Chemistry.

Test Centre(s): The Departmental Test shall be held at Aligarh (U.P.) only.

Course Details:
Row 1: Duration=4 Semesters; Course Code=MBMGA; Intake=10+3*+2^

Source Pages: AMU Guide to Admissions 2026-27, page B.1 (physical page 70)
```

### LLM answer

Based on the information in the guide, the postgraduate course that matches a B.Sc. in Computer Science is:

- **Master of Computer Science and Applications (MCA)** – qualifies for candidates with a 3‑ or 4‑year B.Sc. in Computer Science (or related subjects) who meet the specified subject and marks criteria. [SOURCE 1]

### Sources

- `[SOURCE 1]` Master of Computer Science and Applications (MCA) - Complete Course Information — page B.25
- `[SOURCE 2]` Master of Technology (M. Tech.) – Computer Science & Engineering - Complete Course Information — page B.11
- `[SOURCE 3]` M.Sc. (Ag.) Microbiology - Complete Course Information — page B.1

## 8. Tell me the available Diploma in Engineering branches, duration and intake.

**Retrieval mode:** hybrid retrieval

**Expanded query:** Tell me the available Diploma in Engineering branches, duration and intake.

### Retrieved context

```text
[SOURCE 1]
Title: Diploma in Engineering - Complete Course Information
Citation: AMU Guide to Admissions 2026-27, page D.1
Content:
Course: Diploma in Engineering
Faculty: Faculty of Engineering & Technology
Programme Level: diploma
Record Type: Course Profile

Qualifying Examination: Secondary School Certificate of this University or an equivalent examination with not less than 45% marks in aggregate of English, Maths and Science as three subjects of equal weightage. Further, the candidate should have passed English, Maths and Science individually at the qualifying examination. OR A higher examination with English, Physics, Chemistry and Maths as subjects, with not less than 45% marks in aggregate of English, Physics, Chemistry and Maths of equal weightage. Note: The Status (Internal / External) will only be determined on the basis of High School or its equivalent Examination only.

Age Limit: The age of the candidate must not exceed 21 years as on 1 st July in the year of admission

Selection Process: Through Admission Test

Test Paper Details: There shall be one objective type paper of 100 marks comprising 100 questions with the following breakup : (a) Science (Physics, Chemistry and Life Science) : 50 Marks (b) Mathematics : 30 Marks (c) General Knowledge : 05 Marks (d) English : 05 Marks (e) Indo-Islamic Culture : 10 Marks

Test Centre(s): The Admission Test shall be held at Aligarh (U.P.), Lucknow (U.P.), Meerut (U.P.), Rampur (U.P.), Srinagar (J. & K.), Kolkata (W.B.), Patna (Bihar), Kozhikode (Kerala), Murshidabad (W.B.), Kishanganj (Bihar) & Imphal (Manipur).

Additional Information: a) The test paper shall be available in three languages- English, Hindi and Urdu. b) There shall be a Combined Admission Test for admission to Diploma in Engineering and Senior Secondary School Certificate (Science Stream) . c) Industry Sponsored Category Candidates by the listed companies in Leather Goods & Footwear Technology course shall have to pay a sum of Rs. 25,000/- per student in addition to normal admission charges for the full duration of the course as Extra Development Charges. Such candidates need to give their option for sponsored admission in the Application Form and they must appear in the Combined Admission Test of Diploma in Engineering. Their merit will be determined amongst themselves. They should also download the relevant Appendix Form (Link), fill it and send completed Appendix to the Principal, University Polytechnic (Boys), AMU, Aligarh in a separate cover through Registered / Speed Post.

Course Details:
Row 1: Duration=6 Semesters; Branch Name=Civil Engineering; Course Code=CEDEA; Intake Male=90; Intake Female=---
Row 2: Duration=6 Semesters; Branch Name=Communication Engineering; Course Code=CMDEA; Intake Male=---; Intake Female=15+2^
Row 3: Duration=6 Semesters; Branch Name=Computer Engineering; Course Code=CODEA; Intake Male=---; Intake Female=30+3^
Row 4: Duration=6 Semesters; Branch Name=Computer Science & Engineering; Course Code=CSDEA; Intake Male=30; Intake Female=---
Row 5: Duration=6 Semesters; Branch Name=Electrical Engineering; Course Code=EEDEA; Intake Male=30; Intake Female=---
Row 6: Duration=6 Semesters; Branch Name=Electronics Engineering; Course Code=ELDEA; Intake Male=---; Intake Female=30+3^
Row 7: Duration=6 Semesters; Branch Name=Electronics & Communication Engineering; Course Code=ECDEA; Intake Male=30; Intake Female=---
Row 8: Duration=6 Semesters; Branch Name=Information Technology; Course Code=ITDEA; Intake Male=---; Intake Female=15+2^
Row 9: Duration=6 Semesters; Branch Name=Electrical & Instrumentation Engineering; Course Code=EIDEA; Intake Male=30; Intake Female=---
Row 10: Duration=6 Semesters; Branch Name=Mechanical Engineering; Course Code=MEDEA; Intake Male=125; Intake Female=---
Row 11: Duration=6 Semesters; Branch Name=Architecture; Course Code=ARDEA; Intake Male=14; Intake Female=6**
Row 12: Duration=6 Semesters; Branch Name=Interior Design; Course Code=IDDEA; Intake Male=14; Intake Female=6**+3^
Row 13: Duration=6 Semesters; Branch Name=Leather Goods & Footwear Technology; Course Code=LGDEA; Intake Male=16+5*; Intake Female=9**

Source Pages: AMU Guide to Admissions 2026-27, page D.1 (physical page 110)
```

### LLM answer

**Diploma in Engineering – Branches, Duration & Intake (AMU Guide 2026‑27, page D.1)**  

| Branch | Duration | Intake (Male / Female) |
|--------|----------|------------------------|
| Civil Engineering | 6 semesters | 90 / – |
| Communication Engineering | 6 semesters | – / 15+2^ |
| Computer Engineering | 6 semesters | – / 30+3^ |
| Computer Science & Engineering | 6 semesters | 30 / – |
| Electrical Engineering | 6 semesters | 30 / – |
| Electronics Engineering | 6 semesters | – / 30+3^ |
| Electronics & Communication Engineering | 6 semesters | 30 / – |
| Information Technology | 6 semesters | – / 15+2^ |
| Electrical & Instrumentation Engineering | 6 semesters | 30 / – |
| Mechanical Engineering | 6 semesters | 125 / – |
| Architecture | 6 semesters | 14 / 6** |
| Interior Design | 6 semesters | 14 / 6**+3^ |
| Leather Goods & Footwear Technology | 6 semesters | 16+5* / 9** |

*All durations are 6 semesters. Intake figures are taken directly from the course profile table in the guide.* [SOURCE 1]

### Sources

- `[SOURCE 1]` Diploma in Engineering - Complete Course Information — page D.1
