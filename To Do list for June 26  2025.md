To Do list for June 26, 2025.

0. This is a delicate and some local problem. Based on current guideline, '*oropharyngeal*.pdf', staging various HPV infection. However, our model did not asks about this. It might be related to that insufficient embedding or retrieval. Or, insufficient understanding of guideline by the model. This is quite a local problem, but can be extended differently in other guidelines/cancer types. 

1. We are using JSON format for context, input and ouptut. Check this https://ollama.com/blog/structured-outputs. It might be helpful, but maybe we are already using it. 
https://platform.openai.com/docs/guides/structured-outputs?api-mode=chat This is for openAI version. 

2. In some cases, the model decided T staging and not sure N staging (eg. T2NX), it asks question for user. After got the response, I found model run T and N staging again, both. 
If we decide T stage with high confidence, we don't need to run T staging again. THis would be the case for TXN2. If we have TXNX, than we have to run both.

3. Currently we only have one guideline, but I will extend into multiple guidelines, according to various body parts and cancer types. In this case, we tozenize guidelines separately, and using the bodypart context, we choose which guideline will be used. 
For this process, we might need some rule-based approach, but it is fine, just for this selection. Anyway, we need to prepare this, for later extension. 

4. This is an example report. Report generating agent follow this format. You may modify this for zeroshot learning. Because local model has small capability, we need a good optimzed prompt.

FINDINGS:
Primary Tumor:
There is an enhancing mass centered in the right palatine tonsil measuring 3.2 x 2.8 x 3.5 cm (AP x TR x CC). The mass demonstrates intermediate T1 signal intensity, heterogeneous T2 hyperintensity, and avid contrast enhancement. The lesion extends medially to involve the right soft palate and inferiorly to the right tongue base. There is effacement of the right parapharyngeal fat without definite invasion. The mass abuts but does not clearly invade the medial pterygoid muscle.
Lymph Nodes:
Right neck: Multiple pathologically enlarged lymph nodes are present. Level II: Largest node measures 2.4 x 1.8 cm with central necrosis and peripheral enhancement. Additional nodes at this level measure up to 1.5 cm. Level III: Two nodes measuring 1.2 cm and 0.9 cm with loss of fatty hilum. Level IV: Single borderline node measuring 1.0 cm.
Left neck: Level II: Single reactive-appearing node measuring 0.8 cm with preserved fatty hilum. No pathologically enlarged nodes identified.
Retropharyngeal nodes: No pathologically enlarged retropharyngeal nodes identified.
Vascular Structures: [only significant descriptions should be here]
The carotid arteries and jugular veins are patent bilaterally. The right internal jugular vein is mildly compressed by the level II nodal mass without thrombosis.
Other Structures: [other not-very-significant descriptions]

Nasopharynx: Normal appearance
Oral cavity: Normal aside from described tongue base involvement
Hypopharynx: Normal appearance
Larynx: Normal appearance
Major salivary glands: Normal bilaterally
Thyroid gland: Normal appearance
Visualized skull base: No osseous erosion or marrow signal abnormality

IMPRESSION: [combine staging and rationale]

Right tonsillar mass measuring 3.2 x 2.8 x 3.5 cm with extension to the soft palate and tongue base, consistent with known squamous cell carcinoma. Findings suggest T2 disease (tumor > 2 cm but ≤ 4 cm).
Multiple pathologically enlarged right cervical lymph nodes with the largest measuring 2.4 cm at level II demonstrating central necrosis, consistent with metastatic disease (N2b).
Overall radiologic staging: T2 N2b, clinical stage IVA 
