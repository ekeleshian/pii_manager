"""
DONE:
* removed back_trans altogether to experiment on the combo of two strategies: 
1 - Replace all stagnant entities like PERSON, EMAIL, PHONE_NUMBER
2 - Replace non-stagnant entities by mapping them to their translation. 
    Idea here is that we hard code the translations for non-stagnant entities and replace them via this mapping. Example of this 
    implementation is in lines 172-179 covering the case for possessive pronouns
TODO:
* detect all the other types of PII covered by presideo, and use male/female/non-binary names provdied by faker based on deteced gender
* swap religion, ethnicity, obtain words from wordnet
* improve strategy on gender swapping with regards to profession
* remove textblob dependency as it using google api
* implement multithreading to handle multiple document processing
"""

from textblob import TextBlob
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities.engine.operator_config import OperatorConfig
from faker import Faker
from faker.providers import internet
from presidio_analyzer import PatternRecognizer
import langid
from nltk.corpus import stopwords
from copy import deepcopy


STAGNANT_ENTITIES = {"PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "DOMAIN_NAME"}

stopwords_en = set(stopwords.words('english'))
faker = Faker('en_US')
faker.add_provider(internet)
titles_recognizer = PatternRecognizer(supported_entity='TITLE', deny_list=["Mr.", "Mrs.", "Miss"])

pronoun_recognizer = PatternRecognizer(supported_entity='PRONOUN', deny_list=['he', 'He', 'she', 'She'])
poss_pronoun_recognizer = PatternRecognizer(supported_entity="POSSESSIVE_PRONOUN", deny_list=["his", "her", "His", "Her", 'hers', 'Hers'])

pronoun_swap = {'he': 'she', 'He': 'She', 'his': 'her', 'His': 'Her', \
                'she': 'he', 'She': 'He', 'her': 'his', 'hers': 'his', \
                'Her': 'His', 'Hers': 'His'}

poss_pronoun_swap = {'his': 'her', "His": "Her", "Her": "His", "her": "his"}

title_swap = {'Mr.': "Mrs.", "Mrs.": "Mr.", "Miss": "Mrs."}


## experimentation below
pronoun_swap_ = { 
'he': \
{'ro': {'el' : 'ea'}, 
'es': {'él': 'ella'}}, 
'she': \
{'ro': {'ea': 'el'}, 
'es': {'ella': 'él'}}
}

## experimentation below
poss_pronoun_swap_ = {
	'his': \
	{'ro': {'ale sale': 'ale ei'}}
}

# experimentation below
title_swap_ = {
'Mr.': \
{'ro': {'Domnul' : 'Doamna'}, 
'es': {'Señor': 'Señora'}}, 
'Mrs.': \
{'ro': {'Doamna': 'Domnul'}, 
'es': {'Señora': 'Señor'}},
'Dr.' : \
{'ro': {'Doctor': "Doctor", "Dr.": "Dr."},
'es': {'Doctora': 'Doctor', 'Doctor': 'Doctora'}}
}

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()
analyzer.registry.add_recognizer(titles_recognizer)
analyzer.registry.add_recognizer(pronoun_recognizer)
analyzer.registry.add_recognizer(poss_pronoun_recognizer)



def langid_ext(s1, en_lang_cutoff=0.1):
	lang='en'
	sArr = s1.split()
	if len([s2 for s2 in sArr if s2.strip("' 0123456789¯_§½¼¾×|†—~”—±′–’°−{}[]·-\'?,./<>!@#^&*()+-‑=:;`→¶'") in stopwords_en])/len(sArr) >= en_lang_cutoff:
		lang = 'en'
	else:
		try:
			lang = langid.classify(s1)[0]
			print('else block')
		except Exception as e:
			print(e)
			lang = ''
		if lang != 'en':
			ln = len(s1)
			if ln < 20:
				return lang
			try:
				lang = langid.classify(s1[:int(ln/2)])[0]
				lang2 = langid.classify(s1[int(ln/2):])[0]
				if lang == 'en' or lang2 == 'en':
					lang = 'en'
			except Exception as e:
				print('*****\n')
				print(e)
				lang = 'en'
	return lang


def anonymize_faker_lambda(analyzer_results, text_to_anonymize):
	anonymized_results = anonymizer.anonymize(
		text = text_to_anonymize,
		analyzer_results=analyzer_results,
		operators={"DEFAULT": OperatorConfig("replace", {"new_value": "<UNK>"}), \
		"PERSON": OperatorConfig("custom", {'lambda': lambda x: faker.name()}), \
		"TITLE": OperatorConfig("custom", {'lambda': lambda x: title_swap.get(x, "Mrs.")}), \
		"PRONOUN": OperatorConfig("custom", {'lambda': lambda x: pronoun_swap.get(x, "they")}), \
		"PHONE_NUMBER": OperatorConfig("custom", {"lambda": lambda x: faker.phone_number()}), \
		"EMAIL_ADDRESS": OperatorConfig("custom", {"lambda": lambda x: faker.safe_email()}), \
		"POSSESSIVE_PRONOUN": OperatorConfig("custom", {'lambda': lambda x: pronoun_swap.get(x, 'their')})
		}
	)
	return anonymized_results


def back_trans(x, intermediate='pt', to='en'):

	x1 = x
	x = TextBlob(x).translate(to=intermediate)

	x3 = str(x.translate(to='en'))
	if to != 'en':
		x4 = str(TextBlob(x3).translate(to=to))
		print("*****\n", x1, "=>", x, "=>", x3, "=>", x4)
		return x4
	else:
		print("*****\n", x1, "=>", x, "=>", x3)
		return x3



# text blob uses googletrans. we wll need somethingn that doesn't depend on the api 

def swap_entities(results, orig_str, en_str, origin_lang):
	new_str = orig_str
	for res in results:
		entity = en_str[res.start:res.end]
		start_idx = new_str.find(entity)
		if res.entity_type in STAGNANT_ENTITIES:
			if res.entity_type == "PHONE_NUMBER":
				new_phone = faker.phone_number()
				new_str = new_str[:start_idx] + new_phone + new_str[start_idx + len(entity):]
			elif res.entity_type == "EMAIL_ADDRESS":
				new_email = faker.safe_email()
				new_str = new_str[:start_idx] + new_email + new_str[start_idx + len(entity):]
			elif res.entity_type == "PERSON":
				new_name = faker.name()
				new_str = new_str[:start_idx] + new_name + new_str[start_idx + len(entity):]
		elif origin_lang != 'en':
			if res.entity_type == "POSSESSIVE_PRONOUN":
				# indexing off zero because assuming it is one - to - one (one translation per entity)
				entity_foreign = list(poss_pronoun_swap_.get(entity, {}).get(origin_lang, {}).keys())[0]
				start_idx = new_str.find(entity_foreign)

				new_poss_pronoun = poss_pronoun_swap_.get(entity, {}).get(origin_lang, {}).get(entity_foreign, '')
				new_str = new_str[:start_idx] + new_poss_pronoun + new_str[start_idx + len(entity_foreign):]

		elif origin_lang == 'en':
			if res.entity_type == "PRONOUN":
				new_pronoun = pronoun_swap.get(entity, 'they')
				new_str = new_str[:start_idx] + new_pronoun + new_str[start_idx + len(entity):]
			elif res.entity_type == "POSSESSIVE_PRONOUN":
				new_poss_pronoun = poss_pronoun_swap.get(entity, 'their')
				new_str = new_str[:start_idx] + new_poss_pronoun + new_str[start_idx + len(entity):]
			elif res.entity_type == "TITLE":
				new_title = title_swap.get(entity, 'Mx')
				new_str = new_str[:start_idx] + new_title + new_str[start_idx + len(entity):]

	return new_str






if __name__ == "__main__":
	# text_to_anonymize = 'Mr. Jones is a doctor, and he has the following phone number: 713-333-0565 and his two emails are: email1@contoso.com and email2@contoso.com'
	text_to_anonymize = "Domnul Vexe este medic și are următorul număr de telefon: 713-333-0565, iar cele două e-mailuri ale sale sunt: ​​email1@contoso.com și email2@contoso.com"
	# text_to_anonymize = "Se llamo Elizabeth y su numero de telefóno es +1 (555) 555 - 5555 y su e-mail es foo@bar.com."

	origin_lang = langid_ext(text_to_anonymize)
	print(f'origin_lang: {origin_lang}\n\n')
	if origin_lang != 'en':
		print(f'detected lang, {origin_lang}')
		text_to_anonymize_en = str(TextBlob(text_to_anonymize).translate(to='en'))
	else:
		text_to_anonymize_en = text_to_anonymize

	print(text_to_anonymize_en)
	print('*****************************\n')

	analyzer_results = analyzer.analyze(text=text_to_anonymize_en, language='en')

	new_text = swap_entities(analyzer_results, text_to_anonymize, text_to_anonymize_en, origin_lang)

	print(new_text)
	# anonymized_results = anonymize_faker_lambda(analyzer_results, text_to_anonymize_en)
	# s9 = anonymized_results.text
	# # breakpoint()
	# print(s9)
	# print(back_trans(s9, to=origin_lang))
	# #an idea to improve back_trans is that since we know what slots we are replacing,
	# #we can align with the original sentence in the original language, 
	# #and then inserted the translated slots.

	# if False:
	# # experiment with other types of text aug.
	# #TODO, make sure the embedding swap doesn't translate to non-english words.
	# 	aug = EmbeddingAugmenter(pct_words_to_swap=0.1, transformations_per_example=3)

	# 	s= [back_trans(s1, to=origin_lang) for s1 in aug.augment(s)]
	# 	print(s)

	# # experiment to get gender balanced sentences for lang that are gender cased. For example, "You are a docotor" in Portuguese might be "You (male) are a docotor."
	# # we translate to english, which becomes gender neutral. "You are a doctor.", inject gender "You are a woman and doctor", "You are a man and doctor", then get translation to portuguese. 
	# # align the words between portuguese and english, and remove portugese words corresponding to "a man and" and "a woman and". Now we have created gender balanced sentences. 
	# if False:
	# 	s = "You are a nice woman and doctor"
	# 	s= [back_trans(s1) for s1 in aug.augment(s)]
	# 	print(s) 		










