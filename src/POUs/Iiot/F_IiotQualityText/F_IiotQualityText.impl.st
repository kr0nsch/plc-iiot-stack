CASE eQuality OF
    E_IiotQuality.Good:
        F_IiotQualityText := 'good';
    E_IiotQuality.Uncertain:
        F_IiotQualityText := 'uncertain';
ELSE
    F_IiotQualityText := 'bad';
END_CASE
