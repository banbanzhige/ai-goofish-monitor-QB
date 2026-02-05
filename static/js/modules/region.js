﻿function validateTaskFiltersForm(provinceId, cityId, districtId, publishSelectId) {
    const publishSelect = document.getElementById(publishSelectId);
    const publishValue = publishSelect ? publishSelect.value.trim() : '';

    if (publishValue) {
        const allowedValues = new Set(['1天内', '3天内', '7天内', '14天内']);
        if (!allowedValues.has(publishValue)) {
            Notification.warning('新发布时间选项无效，请重新选择');
            return false;
        }
    }

    const province = document.getElementById(provinceId)?.value || '';
    const city = document.getElementById(cityId)?.value || '';
    const district = document.getElementById(districtId)?.value || '';
    const regionValue = buildRegionValue(province, city, district);

    if (regionValue) {
        const regionPattern = /^[\u4e00-\u9fa5]+(\/[\u4e00-\u9fa5]+)*$/;
        if (!regionPattern.test(regionValue)) {
            Notification.warning('区域格式不正确，请使用"省/市/区"格式');
            return false;
        }
    }

    return true;
}

function buildRegionValue(province, city, district) {
    const parts = [province, city, district]
        .map(value => (value || '').trim().replace(/(省|市)$/u, ''))
        .filter(Boolean);
    return parts.join('/');
}

async function fetchChinaIndex() {
    const response = await fetch('/static/china/index.json');
    if (!response.ok) {
        throw new Error('无法加载省份列表');
    }
    return await response.json();
}

async function fetchChinaProvinceFile(filename) {
    const response = await fetch(`/static/china/${encodeURIComponent(filename)}`);
    if (!response.ok) {
        throw new Error('无法加载省份数据');
    }
    return await response.json();
}

function parseRegionValue(regionValue) {
    if (!regionValue) {
        return { province: '', city: '', district: '' };
    }
    const parts = regionValue.split('/').map(part => part.trim());
    return {
        province: parts[0] || '',
        city: parts[1] || '',
        district: parts[2] || '',
    };
}

function pickRegionOption(value, options) {
    if (!value) return '';
    const exact = options.find(option => option === value);
    if (exact) return exact;
    const startsWith = options.find(option => option.startsWith(value));
    if (startsWith) return startsWith;
    const includes = options.find(option => option.includes(value));
    return includes || value;
}

function isMunicipality(name) {
    return ['北京', '上海', '天津', '重庆', '北京市', '上海市', '天津市', '重庆市'].includes(name);
}

function normalizeRegionNameForAll(name) {
    if (!name) return '';
    const mappings = {
        '内蒙古自治区': '内蒙古',
        '广西壮族自治区': '广西',
        '宁夏回族自治区': '宁夏',
        '新疆维吾尔自治区': '新疆',
        '西藏自治区': '西藏',
        '香港特别行政区': '香港',
        '澳门特别行政区': '澳门',
    };
    if (mappings[name]) {
        return mappings[name];
    }
    return name.replace(/(省|市)$/u, '');
}

function buildAllRegionLabel(name) {
    const normalized = normalizeRegionNameForAll(name);
    return normalized ? `全${normalized}` : '';
}

function prependAllOption(items, allLabel) {
    if (!allLabel) return items;
    if (items.includes(allLabel)) return items;
    return [allLabel, ...items];
}

function toggleMunicipalityUI(citySelect, districtSelect, isMunicipalityRegion, placeholder) {
    if (!citySelect || !districtSelect) return;
    citySelect.disabled = isMunicipalityRegion;
    if (isMunicipalityRegion) {
        citySelect.value = placeholder || '';
    }
}

function populateSelect(selectEl, items, placeholder) {
    if (!selectEl) return;
    selectEl.innerHTML = '';
    const placeholderOption = document.createElement('option');
    placeholderOption.value = '';
    placeholderOption.textContent = placeholder;
    selectEl.appendChild(placeholderOption);
    items.forEach(item => {
        const option = document.createElement('option');
        option.value = item;
        option.textContent = item;
        selectEl.appendChild(option);
    });

}

async function hydrateRegionSelectors({ provinceId, cityId, districtId, regionValue }) {
    const provinceSelect = document.getElementById(provinceId);
    const citySelect = document.getElementById(cityId);
    const districtSelect = document.getElementById(districtId);

    if (!provinceSelect || !citySelect || !districtSelect) return;

    const { province, city, district } = parseRegionValue(regionValue);
    const index = await fetchChinaIndex();
    const provinces = index.map(item => item.name);
    populateSelect(provinceSelect, provinces, '省/自治区/直辖市');

    const normalizedProvince = pickRegionOption(province, provinces);
    provinceSelect.value = normalizedProvince;

    if (!normalizedProvince) {
        populateSelect(citySelect, [], '市/地区');
        populateSelect(districtSelect, [], '区/县');
        return;
    }

    const provinceEntry = index.find(item => item.name === normalizedProvince);
    if (!provinceEntry) return;

    const provinceData = await fetchChinaProvinceFile(provinceEntry.file);
    const cities = (provinceData.children || []).map(item => item.name);
    const municipality = isMunicipality(normalizedProvince);
    const cityPlaceholder = municipality ? '市辖区' : '市/地区';
    const allProvinceLabel = buildAllRegionLabel(normalizedProvince);
    const cityOptions = prependAllOption(cities, allProvinceLabel);
    populateSelect(citySelect, cityOptions, cityPlaceholder);
    let adjustedCity = city;
    let adjustedDistrict = district;
    if (municipality && adjustedCity && !adjustedDistrict) {
        // 直辖市只选到第二级时，将“城市”理解为区县
        adjustedDistrict = adjustedCity;
        adjustedCity = allProvinceLabel || adjustedCity;
    }
    const normalizedCity = pickRegionOption(adjustedCity, cityOptions) || allProvinceLabel || (municipality ? (cities[0] || '') : '');
    citySelect.value = normalizedCity;
    toggleMunicipalityUI(citySelect, districtSelect, municipality, cityPlaceholder);
    toggleMunicipalityUI(citySelect, districtSelect, municipality, cityPlaceholder);

    const isAllProvince = normalizedCity && normalizedCity === allProvinceLabel;
    if (!normalizedCity || (!municipality && isAllProvince)) {
        populateSelect(districtSelect, [], '区/县');
        return;
    }

    const effectiveCityName = (municipality && isAllProvince) ? (cities[0] || '') : normalizedCity;
    const cityEntry = (provinceData.children || []).find(item => item.name === effectiveCityName);
    const districts = cityEntry ? (cityEntry.children || []).map(item => item.name) : [];
    const allCityLabel = buildAllRegionLabel(effectiveCityName);
    const districtOptions = prependAllOption(districts, allCityLabel);
    populateSelect(districtSelect, districtOptions, '区/县');
    districtSelect.value = pickRegionOption(adjustedDistrict, districtOptions) || (allCityLabel || '');
}

async function setupRegionSelectors({ provinceId, cityId, districtId, regionValue }) {
    const provinceSelect = document.getElementById(provinceId);
    const citySelect = document.getElementById(cityId);
    const districtSelect = document.getElementById(districtId);

    if (!provinceSelect || !citySelect || !districtSelect) return;

    let indexCache = null;
    let provinceDataCache = null;

    const loadIndex = async () => {
        if (!indexCache) {
            indexCache = await fetchChinaIndex();
        }
        return indexCache;
    };

    const loadProvinceData = async (provinceName) => {
        if (!provinceName) return null;
        if (provinceDataCache && provinceDataCache.name === provinceName) {
            return provinceDataCache.data;
        }
        const index = await loadIndex();
        const entry = index.find(item => item.name === provinceName);
        if (!entry) return null;
        const data = await fetchChinaProvinceFile(entry.file);
        provinceDataCache = { name: provinceName, data };
        return data;
    };

    provinceSelect.addEventListener('change', async () => {
        const provinceName = provinceSelect.value;
        populateSelect(citySelect, [], '市/地区');
        populateSelect(districtSelect, [], '区/县');
        if (!provinceName) return;
        const provinceData = await loadProvinceData(provinceName);
        const cities = (provinceData?.children || []).map(item => item.name);
        const municipality = isMunicipality(provinceName);
        const allProvinceLabel = buildAllRegionLabel(provinceName);
        const cityOptions = prependAllOption(cities, allProvinceLabel);
        populateSelect(citySelect, cityOptions, municipality ? '市辖区' : '市/地区');
        if (allProvinceLabel) {
            citySelect.value = allProvinceLabel;
        }
        if (municipality) {
            citySelect.value = allProvinceLabel || (cities[0] || '');
            citySelect.dispatchEvent(new Event('change'));
        }
        toggleMunicipalityUI(citySelect, districtSelect, municipality, municipality ? '市辖区' : '');
    });

    citySelect.addEventListener('change', async () => {
        const provinceName = provinceSelect.value;
        const cityName = citySelect.value;
        populateSelect(districtSelect, [], '区/县');
        if (!provinceName || !cityName) return;
        const provinceData = await loadProvinceData(provinceName);
        const rawCities = (provinceData?.children || []).map(item => item.name);
        const municipality = isMunicipality(provinceName);
        const allProvinceLabel = buildAllRegionLabel(provinceName);
        const isAllProvince = cityName === allProvinceLabel;
        if (!municipality && isAllProvince) {
            return;
        }
        const effectiveCityName = (municipality && isAllProvince) ? (rawCities[0] || '') : cityName;
        const cityEntry = (provinceData?.children || []).find(item => item.name === effectiveCityName);
        const districts = cityEntry ? (cityEntry.children || []).map(item => item.name) : [];
        const allCityLabel = buildAllRegionLabel(effectiveCityName);
        const districtOptions = prependAllOption(districts, allCityLabel);
        populateSelect(districtSelect, districtOptions, '区/县');
        if (allCityLabel) {
            districtSelect.value = allCityLabel;
        }
    });

    await hydrateRegionSelectors({ provinceId, cityId, districtId, regionValue });
}

async function hydrateAdvancedFilterSelectors(cell, taskData) {
    const provinceSelect = cell.querySelector('.filter-region-province');
    const citySelect = cell.querySelector('.filter-region-city');
    const districtSelect = cell.querySelector('.filter-region-district');
    if (!provinceSelect || !citySelect || !districtSelect) return;

    const { province, city, district } = parseRegionValue(taskData.region || '');
    const index = await fetchChinaIndex();
    const provinces = index.map(item => item.name);
    populateSelect(provinceSelect, provinces, '省/自治区/直辖市');
    const normalizedProvince = pickRegionOption(province, provinces);
    provinceSelect.value = normalizedProvince;

    provinceSelect.onchange = async () => {
        const provinceName = provinceSelect.value;
        populateSelect(citySelect, [], '市/地区');
        populateSelect(districtSelect, [], '区/县');
        if (!provinceName) return;
        const provinceEntry = index.find(item => item.name === provinceName);
        if (!provinceEntry) return;
        const updatedProvince = await fetchChinaProvinceFile(provinceEntry.file);
        const updatedCities = (updatedProvince.children || []).map(item => item.name);
        const municipality = isMunicipality(provinceName);
        const allProvinceLabel = buildAllRegionLabel(provinceName);
        const cityOptions = prependAllOption(updatedCities, allProvinceLabel);
        populateSelect(citySelect, cityOptions, municipality ? '市辖区' : '市/地区');
        if (allProvinceLabel) {
            citySelect.value = allProvinceLabel;
        }
        if (municipality) {
            citySelect.value = allProvinceLabel || (updatedCities[0] || '');
            citySelect.dispatchEvent(new Event('change'));
        }
        toggleMunicipalityUI(citySelect, districtSelect, municipality, municipality ? '市辖区' : '');
    };

    citySelect.onchange = async () => {
        const provinceName = provinceSelect.value;
        const cityName = citySelect.value;
        populateSelect(districtSelect, [], '区/县');
        if (!provinceName || !cityName) return;
        const provinceEntry = index.find(item => item.name === provinceName);
        if (!provinceEntry) return;
        const updatedProvince = await fetchChinaProvinceFile(provinceEntry.file);
        const rawCities = (updatedProvince.children || []).map(item => item.name);
        const municipality = isMunicipality(provinceName);
        const allProvinceLabel = buildAllRegionLabel(provinceName);
        const isAllProvince = cityName === allProvinceLabel;
        if (!municipality && isAllProvince) {
            return;
        }
        const effectiveCityName = (municipality && isAllProvince) ? (rawCities[0] || '') : cityName;
        const updatedCity = (updatedProvince.children || []).find(item => item.name === effectiveCityName);
        const updatedDistricts = updatedCity ? (updatedCity.children || []).map(item => item.name) : [];
        const allCityLabel = buildAllRegionLabel(effectiveCityName);
        const districtOptions = prependAllOption(updatedDistricts, allCityLabel);
        populateSelect(districtSelect, districtOptions, '区/县');
        if (allCityLabel) {
            districtSelect.value = allCityLabel;
        }
    };

    if (!normalizedProvince) {
        populateSelect(citySelect, [], '市/地区');
        populateSelect(districtSelect, [], '区/县');
        return;
    }

    const provinceEntry = index.find(item => item.name === normalizedProvince);
    if (!provinceEntry) return;
    const provinceData = await fetchChinaProvinceFile(provinceEntry.file);
    const cities = (provinceData.children || []).map(item => item.name);
    const municipality = isMunicipality(normalizedProvince);
    const cityPlaceholder = municipality ? '市辖区' : '市/地区';
    const allProvinceLabel = buildAllRegionLabel(normalizedProvince);
    const cityOptions = prependAllOption(cities, allProvinceLabel);
    populateSelect(citySelect, cityOptions, cityPlaceholder);
    let adjustedCity = city;
    let adjustedDistrict = district;
    if (municipality && adjustedCity && !adjustedDistrict) {
        adjustedDistrict = adjustedCity;
        adjustedCity = allProvinceLabel || adjustedCity;
    }
    const normalizedCity = pickRegionOption(adjustedCity, cityOptions) || allProvinceLabel || (municipality ? (cities[0] || '') : '');
    citySelect.value = normalizedCity;

    const isAllProvince = normalizedCity && normalizedCity === allProvinceLabel;
    if (!normalizedCity || (!municipality && isAllProvince)) {
        populateSelect(districtSelect, [], '区/县');
    } else {
        const effectiveCityName = (municipality && isAllProvince) ? (cities[0] || '') : normalizedCity;
        const cityEntry = (provinceData.children || []).find(item => item.name === effectiveCityName);
        const districts = cityEntry ? (cityEntry.children || []).map(item => item.name) : [];
        const allCityLabel = buildAllRegionLabel(effectiveCityName);
        const districtOptions = prependAllOption(districts, allCityLabel);
        populateSelect(districtSelect, districtOptions, '区/县');
        districtSelect.value = pickRegionOption(adjustedDistrict, districtOptions) || (allCityLabel || '');
    }

}
